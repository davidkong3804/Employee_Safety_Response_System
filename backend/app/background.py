"""Background write-buffer drainer.

Runs one asyncio Task per process. Every DRAIN_INTERVAL_SECONDS it scans
Redis for events that have buffered safety-report submissions and flushes
them to PostgreSQL in a single batch UPDATE per event.

Multi-pod safety
----------------
Each pod independently discovers pending events via SCAN and drains them.
Two pods racing on the same event will each see the same directory Set
(buf:events_with_pending:{event_id}), drain overlapping subsets, and issue
idempotent batch UPDATEs — the last writer wins, which is correct
(last-write-wins matches the UniqueConstraint on event_id+user_id).

Graceful shutdown
-----------------
stop_drainer() cancels the loop task then does a final drain pass so that
reports buffered just before pod termination are not lost. Kubernetes sends
SIGTERM → uvicorn triggers ASGI lifespan shutdown → stop_drainer() runs
within the default 30 s termination grace period.
"""
from __future__ import annotations

import asyncio
import logging

from app.cache import _DISABLED, _get_client, drain_event_buffer

log = logging.getLogger(__name__)

DRAIN_INTERVAL_SECONDS: float = 2.0

_drainer_task: asyncio.Task | None = None


async def drain_all_pending_events() -> None:
    """Find every event with buffered reports and drain each one."""
    try:
        client = _get_client()
        event_ids: list[str] = []
        async for key in client.scan_iter(match="buf:events_with_pending:*", count=50):
            event_ids.append(key.split(":")[-1])
    except Exception as exc:
        log.debug("drainer: scan failed: %s", exc)
        return

    for event_id in event_ids:
        try:
            flushed = await drain_event_buffer(event_id)
            if flushed:
                log.info("drainer: event=%s flushed=%d", event_id, flushed)
        except Exception as exc:
            log.warning("drainer: event=%s error: %s", event_id, exc)


async def _drainer_loop() -> None:
    log.info("write-buffer drainer started (interval=%.1fs)", DRAIN_INTERVAL_SECONDS)
    while True:
        await asyncio.sleep(DRAIN_INTERVAL_SECONDS)
        await drain_all_pending_events()


async def start_drainer() -> None:
    """Start the background drainer task. Called from app lifespan startup."""
    global _drainer_task
    if _DISABLED:
        log.info("CACHE_DISABLED=1: write-buffer drainer will not start")
        return
    _drainer_task = asyncio.create_task(_drainer_loop(), name="write-buffer-drainer")


async def stop_drainer() -> None:
    """Stop the drainer and do a final drain pass. Called from app lifespan shutdown."""
    global _drainer_task
    if _drainer_task and not _drainer_task.done():
        _drainer_task.cancel()
        try:
            await _drainer_task
        except asyncio.CancelledError:
            pass
    if not _DISABLED:
        log.info("drainer: final drain on shutdown")
        await drain_all_pending_events()
