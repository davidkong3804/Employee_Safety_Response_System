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
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Corrupt cache entry — pretend it's a miss so the caller refetches.
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
