"""Redis caching utilities for hot read endpoints.

Why this exists
---------------
The Manager Dashboard polls `/api/events/{id}/stats` and
`/api/events/{id}/stats/by-department` every 30 seconds. Under load,
N concurrent managers polling the same endpoint amplify the underlying
SQL aggregate `N×` for queries whose result barely changes between
adjacent polls. A short-TTL Redis cache absorbs the duplicate reads
without delaying real-time updates noticeably — 5 seconds of cache lag
is well within the 30-second poll cadence.

Design notes
------------
* **Best-effort, never required.** Every read/write swallows Redis
  errors so a Redis outage degrades to "uncached" rather than 500.
* **JSON-serialised** on the wire so any consumer can dump/load without
  bringing in a Python-specific format (pickle, msgpack).
* **Pattern-based invalidation.** Writes to an event delete every
  cache key under `stats:event:<id>:*`, so we don't have to enumerate
  every aggregate variant that ever existed.
* **Lazy connection.** First call lazily opens the connection; subsequent
  calls reuse it. The connection is module-global so it lives for the
  process lifetime (lots of short-lived requests share one TCP socket).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import redis.asyncio as redis_async

from app.config import settings

log = logging.getLogger(__name__)

# 5-second TTL on dashboard aggregates. Long enough to absorb dashboard
# bursts (e.g. 30 managers polling within the same second) yet short
# enough that any real-time delta surfaces within the 30-second poll.
DEFAULT_TTL_SECONDS = 5

# Test escape hatch — when set, every cache operation is a no-op so the
# integration suite doesn't have to wait 2× socket_timeout on every cache
# call that would otherwise try to reach a nonexistent Redis. Production
# and Docker Compose both leave this unset, hitting the real Redis.
_DISABLED = os.environ.get("CACHE_DISABLED", "").lower() in ("1", "true", "yes")

_client: Optional[redis_async.Redis] = None


def _get_client() -> redis_async.Redis:
    """Lazy module-global Redis client. Returns the same instance on
    every call within the process.
    """
    global _client
    if _client is None:
        _client = redis_async.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
            # Retry once on timeout so transient Cloud Memorystore hiccups don't
            # immediately surface as errors to callers. The outer try/except still
            # catches any remaining failure and degrades gracefully.
            retry_on_timeout=True,
            # Send periodic PING to detect stale connections before they are used,
            # important for long-lived pods connecting to Memorystore across VPC.
            health_check_interval=30,
        )
    return _client


async def cache_get_json(key: str) -> Optional[Any]:
    """Return parsed JSON value or None on cache miss / Redis error."""
    if _DISABLED:
        return None
    try:
        raw = await _get_client().get(key)
    except Exception as exc:
        log.debug("cache_get_json(%s) failed: %s", key, exc)
        from app.metrics import CACHE_OPERATIONS
        CACHE_OPERATIONS.labels(op="miss").inc()
        return None
    if raw is None:
        from app.metrics import CACHE_OPERATIONS
        CACHE_OPERATIONS.labels(op="miss").inc()
        return None
    try:
        val = json.loads(raw)
        from app.metrics import CACHE_OPERATIONS
        CACHE_OPERATIONS.labels(op="hit").inc()
        return val
    except json.JSONDecodeError:
        # Corrupt cache entry — pretend it's a miss so the caller refetches.
        from app.metrics import CACHE_OPERATIONS
        CACHE_OPERATIONS.labels(op="miss").inc()
        return None


async def cache_set_json(
    key: str,
    value: Any,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Cache a JSON-serialisable value. Failures are silently ignored."""
    if _DISABLED:
        return
    try:
        payload = json.dumps(value, default=str)
        await _get_client().set(key, payload, ex=ttl_seconds)
    except Exception as exc:
        log.debug("cache_set_json(%s) failed: %s", key, exc)


async def cache_invalidate_pattern(pattern: str) -> None:
    """Delete every key matching the glob `pattern` (e.g. 'stats:event:abc:*').

    Uses SCAN so it doesn't block Redis on large keyspaces. Failures are
    silently ignored — stale cache will simply expire after the TTL.
    """
    if _DISABLED:
        return
    try:
        client = _get_client()
        async for key in client.scan_iter(match=pattern, count=200):
            await client.delete(key)
    except Exception as exc:
        log.debug("cache_invalidate_pattern(%s) failed: %s", pattern, exc)


async def cache_delete(key: str) -> None:
    """Delete a specific key from the cache.

    Faster and more efficient than scan-based invalidation when we know the exact key.
    Failures are silently ignored.
    """
    if _DISABLED:
        return
    try:
        await _get_client().delete(key)
    except Exception as exc:
        log.debug("cache_delete(%s) failed: %s", key, exc)


# ---------------------------------------------------------------------------
# Write buffer — absorbs concurrent safety-report submissions under spike load.
#
# Instead of each employee request hammering PostgreSQL with a synchronous
# UPDATE, we write to a Redis Hash and let the background drainer
# (background.py) batch-flush to the DB every 2 seconds.
#
# Key schema:
#   buf:report:{event_id}:{user_id}          Hash  (per-user entry, TTL 60 s)
#   buf:events_with_pending:{event_id}       Set   (directory of pending user_ids, TTL 60 s)
# ---------------------------------------------------------------------------

_BUF_TTL = 60  # seconds — well beyond the 2 s drain interval


async def buffer_report(
    event_id: str,
    user_id: str,
    status: str,
    message: str,
    reported_at: str,
) -> bool:
    """Write one safety-report to the Redis write buffer.

    Returns True on success, False when Redis is unavailable or disabled
    (caller should fall back to a direct DB write).
    """
    if _DISABLED:
        return False
    try:
        import time

        client = _get_client()
        buf_key = f"buf:report:{event_id}:{user_id}"
        dir_key = f"buf:events_with_pending:{event_id}"
        pipe = client.pipeline()
        pipe.hset(
            buf_key,
            mapping={
                "status": status,
                "message": message,
                "reported_at": reported_at,
                "buffered_at": str(time.time()),
            },
        )
        pipe.expire(buf_key, _BUF_TTL)
        pipe.sadd(dir_key, user_id)
        pipe.expire(dir_key, _BUF_TTL)
        await pipe.execute()
        return True
    except Exception as exc:
        log.debug("buffer_report(%s/%s) failed: %s", event_id, user_id, exc)
        return False


async def get_buffered_report(event_id: str, user_id: str) -> dict | None:
    """Read one buffered report without consuming it.

    Called by get_my_report so a read immediately after a buffered write
    returns the not-yet-flushed status instead of the stale DB null.
    """
    if _DISABLED:
        return None
    try:
        client = _get_client()
        buf_key = f"buf:report:{event_id}:{user_id}"
        data = await client.hgetall(buf_key)
        if data and data.get("status"):
            return data
        return None
    except Exception as exc:
        log.debug("get_buffered_report(%s/%s) failed: %s", event_id, user_id, exc)
        return None


async def drain_event_buffer(event_id: str) -> int:
    """Drain all buffered reports for *event_id* into PostgreSQL.

    Returns the number of rows written (0 if nothing was pending or on error).
    Called only by the background drainer task — not on the request path.
    """
    if _DISABLED:
        return 0
    try:
        client = _get_client()
        dir_key = f"buf:events_with_pending:{event_id}"

        # Take ownership of the directory atomically-ish:
        # delete the dir key first so new incoming reports go into a fresh Set,
        # then process the snapshot we just captured.
        user_ids = await client.smembers(dir_key)
        if not user_ids:
            return 0
        await client.delete(dir_key)

        # Batch-read all per-user Hashes.
        user_id_list = list(user_ids)
        pipe = client.pipeline()
        for uid in user_id_list:
            pipe.hgetall(f"buf:report:{event_id}:{uid}")
        raw_results = await pipe.execute()

        records = [
            {
                "user_id": uid,
                "status": hdata["status"],
                "message": hdata.get("message") or None,
                "reported_at": hdata.get("reported_at"),
            }
            for uid, hdata in zip(user_id_list, raw_results)
            if isinstance(hdata, dict) and hdata.get("status")
        ]

        if not records:
            return 0

        # Write to DB FIRST, then clear the buffer. The earlier order (delete
        # buffer, then UPDATE) opened a read-after-drain window: between the
        # delete and the commit, get_my_report saw buffered=None AND DB
        # status=NULL, so the employee's "報告已回報" UI flipped back to the
        # "回報狀態" buttons mid-drain. By delaying the buf:report:* deletes
        # until after the DB commit, get_my_report's overlay still finds the
        # buffered value (which matches what we just wrote to DB) — no
        # null-window flicker.
        count = await _batch_update_db(event_id, records)

        # Now safe to clear the per-user buf keys we just drained.
        del_pipe = client.pipeline()
        for uid in user_id_list:
            del_pipe.delete(f"buf:report:{event_id}:{uid}")
        await del_pipe.execute()

        # Invalidate stats cache once per drain cycle, not once per report.
        await cache_invalidate_pattern(f"stats:event:{event_id}:*")
        return count

    except Exception as exc:
        log.warning("drain_event_buffer(%s) failed: %s", event_id, exc)
        return 0


async def _batch_update_db(event_id: str, records: list[dict]) -> int:
    """Batch-UPDATE safety_reports using a single SQL VALUES list.

    One DB round-trip and one WAL write group for up to thousands of rows,
    vastly cheaper than N individual UPDATEs.

    asyncpg type notes
    ------------------
    * UUID: pass as str + CAST in VALUES — asyncpg accepts str with explicit CAST.
    * report_status enum: pass as str + CAST in VALUES — same approach.
    * timestamptz: asyncpg requires a Python datetime object (not a str), even
      with CAST. We parse the ISO-8601 string stored in Redis before binding.
    * CAST() function syntax throughout — ":name::type" confuses asyncpg's
      parameter parser (the second colon looks like a new param name).
    """
    from datetime import datetime

    from sqlalchemy import text

    from app.database import async_session

    values_parts: list[str] = []
    params: dict = {"event_id": event_id}

    for i, rec in enumerate(records):
        values_parts.append(
            f"(CAST(:uid_{i} AS uuid), CAST(:st_{i} AS report_status), :msg_{i}, CAST(:rat_{i} AS timestamptz))"
        )
        params[f"uid_{i}"] = rec["user_id"]
        params[f"st_{i}"] = rec["status"]
        params[f"msg_{i}"] = rec["message"]
        # asyncpg requires a Python datetime (not str) when CAST(...AS timestamptz)
        # is present — the CAST tells asyncpg to expect a datetime, and we must
        # actually supply one or it rejects the binding.
        params[f"rat_{i}"] = datetime.fromisoformat(rec["reported_at"])

    sql = text(
        f"""
        UPDATE safety_reports
        SET    status      = v.status,
               message     = v.message,
               reported_at = v.reported_at
        FROM   (VALUES {", ".join(values_parts)})
               AS v(user_id, status, message, reported_at)
        WHERE  safety_reports.event_id = CAST(:event_id AS uuid)
          AND  safety_reports.user_id  = v.user_id
        """
    )

    async with async_session() as session:
        result = await session.execute(sql, params)
        await session.commit()
        return result.rowcount if result.rowcount is not None else 0
