"""Unit tests for app/background.py — write-buffer drainer."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import background


@pytest.fixture()
def enable_drainer(monkeypatch):
    """Flip CACHE _DISABLED off so start/stop_drainer actually runs."""
    monkeypatch.setattr(background, "_DISABLED", False)
    yield


@pytest.fixture()
def mock_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(background, "_get_client", lambda: client)
    return client


# ---------------------------------------------------------------------------
# drain_all_pending_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drain_all_pending_events_no_events(enable_drainer, mock_client, monkeypatch):
    """No pending events → drain_event_buffer never called."""
    async def empty_scan(**_kwargs):
        if False:
            yield  # pragma: no cover
    mock_client.scan_iter = empty_scan

    fake_drain = AsyncMock()
    monkeypatch.setattr(background, "drain_event_buffer", fake_drain)

    await background.drain_all_pending_events()
    fake_drain.assert_not_awaited()


@pytest.mark.asyncio
async def test_drain_all_pending_events_iterates_keys(enable_drainer, mock_client, monkeypatch):
    """Two pending event keys → drain_event_buffer called once per event_id."""
    async def fake_scan(**_kwargs):
        for k in ("buf:events_with_pending:evt-1", "buf:events_with_pending:evt-2"):
            yield k
    mock_client.scan_iter = fake_scan

    fake_drain = AsyncMock(side_effect=[3, 0])
    monkeypatch.setattr(background, "drain_event_buffer", fake_drain)

    await background.drain_all_pending_events()
    assert fake_drain.await_count == 2
    fake_drain.assert_any_await("evt-1")
    fake_drain.assert_any_await("evt-2")


@pytest.mark.asyncio
async def test_drain_all_pending_events_swallows_scan_error(enable_drainer, monkeypatch):
    """Redis SCAN failure → function returns silently (best-effort)."""
    def boom():
        raise RuntimeError("redis down")
    monkeypatch.setattr(background, "_get_client", boom)

    fake_drain = AsyncMock()
    monkeypatch.setattr(background, "drain_event_buffer", fake_drain)

    await background.drain_all_pending_events()  # must not raise
    fake_drain.assert_not_awaited()


@pytest.mark.asyncio
async def test_drain_all_pending_events_continues_on_per_event_error(
    enable_drainer, mock_client, monkeypatch
):
    """If one event's drain raises, the next event still gets drained."""
    async def fake_scan(**_kwargs):
        for k in ("buf:events_with_pending:bad", "buf:events_with_pending:good"):
            yield k
    mock_client.scan_iter = fake_scan

    async def drain_side_effect(event_id):
        if event_id == "bad":
            raise RuntimeError("DB hiccup")
        return 5
    fake_drain = AsyncMock(side_effect=drain_side_effect)
    monkeypatch.setattr(background, "drain_event_buffer", fake_drain)

    await background.drain_all_pending_events()  # must not raise
    assert fake_drain.await_count == 2


# ---------------------------------------------------------------------------
# start_drainer / stop_drainer lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_drainer_noop_when_cache_disabled(monkeypatch):
    monkeypatch.setattr(background, "_DISABLED", True)
    monkeypatch.setattr(background, "_drainer_task", None)
    await background.start_drainer()
    assert background._drainer_task is None


@pytest.mark.asyncio
async def test_start_drainer_creates_task_when_enabled(enable_drainer, monkeypatch):
    monkeypatch.setattr(background, "_drainer_task", None)
    fake_drain_all = AsyncMock()
    monkeypatch.setattr(background, "drain_all_pending_events", fake_drain_all)
    monkeypatch.setattr(background, "DRAIN_INTERVAL_SECONDS", 10.0)

    await background.start_drainer()
    task = background._drainer_task
    assert task is not None
    assert not task.done()

    # Tear down: cancel the task so it doesn't leak.
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    monkeypatch.setattr(background, "_drainer_task", None)


@pytest.mark.asyncio
async def test_stop_drainer_cancels_running_task_and_final_drains(
    enable_drainer, monkeypatch
):
    fake_drain_all = AsyncMock()
    monkeypatch.setattr(background, "drain_all_pending_events", fake_drain_all)

    async def never_ending():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
    task = asyncio.create_task(never_ending())
    monkeypatch.setattr(background, "_drainer_task", task)

    await background.stop_drainer()
    assert task.done()
    # Final drain pass was invoked on shutdown.
    fake_drain_all.assert_awaited()


@pytest.mark.asyncio
async def test_stop_drainer_no_task_no_op(monkeypatch):
    """If no drainer was started, stop_drainer should still not raise.

    When CACHE_DISABLED is set, the final drain pass is also skipped.
    """
    monkeypatch.setattr(background, "_DISABLED", True)
    monkeypatch.setattr(background, "_drainer_task", None)
    fake_drain_all = AsyncMock()
    monkeypatch.setattr(background, "drain_all_pending_events", fake_drain_all)

    await background.stop_drainer()
    fake_drain_all.assert_not_awaited()
