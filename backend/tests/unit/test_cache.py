"""Unit tests for app/cache.py — Redis caching + write-buffer helpers.

The integration test suite runs with `CACHE_DISABLED=1` (set in conftest)
so the disabled-path branches are exercised by default. This file flips
the toggle back on per-test, monkeypatching `_get_client` to return a
mock Redis so we can assert behaviour without a live Redis service.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import cache


@pytest.fixture()
def enable_cache(monkeypatch):
    """Flip the module-level _DISABLED flag off for the test."""
    monkeypatch.setattr(cache, "_DISABLED", False)
    yield


@pytest.fixture()
def mock_redis(monkeypatch):
    """Return a MagicMock whose async methods return AsyncMocks."""
    client = MagicMock()
    client.get = AsyncMock()
    client.set = AsyncMock()
    client.delete = AsyncMock()
    client.hset = AsyncMock()
    client.hgetall = AsyncMock()
    client.smembers = AsyncMock()
    client.expire = AsyncMock()
    client.sadd = AsyncMock()

    # pipeline() returns an object whose .execute() is awaitable; intermediate
    # calls (hset, expire, sadd, delete) are synchronous chained no-ops.
    pipe = MagicMock()
    pipe.hset = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.sadd = MagicMock(return_value=pipe)
    pipe.delete = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[])
    client.pipeline = MagicMock(return_value=pipe)

    # scan_iter is an async generator — default to "no keys".
    async def empty_scan(**_kwargs):
        if False:
            yield  # pragma: no cover
    client.scan_iter = empty_scan

    monkeypatch.setattr(cache, "_get_client", lambda: client)
    return client


# ---------------------------------------------------------------------------
# Disabled-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_get_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(cache, "_DISABLED", True)
    assert await cache.cache_get_json("any-key") is None


@pytest.mark.asyncio
async def test_cache_set_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(cache, "_DISABLED", True)
    # Should silently return without raising.
    await cache.cache_set_json("any-key", {"a": 1})


@pytest.mark.asyncio
async def test_cache_delete_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(cache, "_DISABLED", True)
    await cache.cache_delete("any-key")


@pytest.mark.asyncio
async def test_cache_invalidate_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(cache, "_DISABLED", True)
    await cache.cache_invalidate_pattern("stats:event:*")


@pytest.mark.asyncio
async def test_buffer_report_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(cache, "_DISABLED", True)
    ok = await cache.buffer_report("e1", "u1", "safe", "", "2026-01-01T00:00:00+00:00")
    assert ok is False


@pytest.mark.asyncio
async def test_get_buffered_report_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(cache, "_DISABLED", True)
    assert await cache.get_buffered_report("e1", "u1") is None


@pytest.mark.asyncio
async def test_drain_returns_zero_when_disabled(monkeypatch):
    monkeypatch.setattr(cache, "_DISABLED", True)
    assert await cache.drain_event_buffer("e1") == 0


# ---------------------------------------------------------------------------
# cache_get_json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_get_json_hit(enable_cache, mock_redis):
    mock_redis.get.return_value = json.dumps({"safe": 5})
    val = await cache.cache_get_json("stats:event:abc:total")
    assert val == {"safe": 5}
    mock_redis.get.assert_awaited_once_with("stats:event:abc:total")


@pytest.mark.asyncio
async def test_cache_get_json_miss_returns_none(enable_cache, mock_redis):
    mock_redis.get.return_value = None
    assert await cache.cache_get_json("missing") is None


@pytest.mark.asyncio
async def test_cache_get_json_corrupt_value_returns_none(enable_cache, mock_redis):
    mock_redis.get.return_value = "not-json{"
    assert await cache.cache_get_json("corrupt") is None


@pytest.mark.asyncio
async def test_cache_get_json_redis_error_returns_none(enable_cache, mock_redis):
    mock_redis.get.side_effect = RuntimeError("connection refused")
    # Must not raise — best-effort design.
    assert await cache.cache_get_json("any") is None


# ---------------------------------------------------------------------------
# cache_set_json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_set_json_writes_with_default_ttl(enable_cache, mock_redis):
    await cache.cache_set_json("k", {"a": 1})
    mock_redis.set.assert_awaited_once()
    args, kwargs = mock_redis.set.call_args
    assert args[0] == "k"
    assert json.loads(args[1]) == {"a": 1}
    assert kwargs.get("ex") == cache.DEFAULT_TTL_SECONDS


@pytest.mark.asyncio
async def test_cache_set_json_custom_ttl(enable_cache, mock_redis):
    await cache.cache_set_json("k", "v", ttl_seconds=42)
    _, kwargs = mock_redis.set.call_args
    assert kwargs.get("ex") == 42


@pytest.mark.asyncio
async def test_cache_set_json_swallows_redis_errors(enable_cache, mock_redis):
    mock_redis.set.side_effect = RuntimeError("boom")
    # Must not raise.
    await cache.cache_set_json("k", {"a": 1})


# ---------------------------------------------------------------------------
# cache_delete & cache_invalidate_pattern
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_delete_calls_redis(enable_cache, mock_redis):
    await cache.cache_delete("stats:event:abc:total")
    mock_redis.delete.assert_awaited_once_with("stats:event:abc:total")


@pytest.mark.asyncio
async def test_cache_delete_swallows_error(enable_cache, mock_redis):
    mock_redis.delete.side_effect = RuntimeError("boom")
    await cache.cache_delete("k")  # no raise


@pytest.mark.asyncio
async def test_cache_invalidate_pattern_iterates_and_deletes(enable_cache, mock_redis):
    async def fake_scan(**_kwargs):
        for k in ("stats:event:abc:total", "stats:event:abc:dept"):
            yield k
    mock_redis.scan_iter = fake_scan

    await cache.cache_invalidate_pattern("stats:event:abc:*")
    assert mock_redis.delete.await_count == 2


@pytest.mark.asyncio
async def test_cache_invalidate_pattern_handles_scan_failure(enable_cache, mock_redis):
    def boom_scan(**_kwargs):
        raise RuntimeError("scan failed")
    mock_redis.scan_iter = boom_scan
    # Must not raise.
    await cache.cache_invalidate_pattern("p:*")


# ---------------------------------------------------------------------------
# buffer_report / get_buffered_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buffer_report_returns_true_on_success(enable_cache, mock_redis):
    ok = await cache.buffer_report(
        "evt-1", "usr-1", "safe", "", "2026-01-01T00:00:00+00:00"
    )
    assert ok is True
    pipe = mock_redis.pipeline.return_value
    pipe.hset.assert_called_once()
    pipe.sadd.assert_called_once()
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_buffer_report_returns_false_on_redis_error(enable_cache, mock_redis):
    mock_redis.pipeline.return_value.execute.side_effect = RuntimeError("boom")
    ok = await cache.buffer_report("e", "u", "safe", "", "2026-01-01T00:00:00+00:00")
    assert ok is False


@pytest.mark.asyncio
async def test_get_buffered_report_returns_dict_when_present(enable_cache, mock_redis):
    mock_redis.hgetall.return_value = {
        "status": "safe",
        "message": "",
        "reported_at": "2026-01-01T00:00:00+00:00",
    }
    data = await cache.get_buffered_report("e", "u")
    assert data and data["status"] == "safe"


@pytest.mark.asyncio
async def test_get_buffered_report_returns_none_when_empty(enable_cache, mock_redis):
    mock_redis.hgetall.return_value = {}
    assert await cache.get_buffered_report("e", "u") is None


@pytest.mark.asyncio
async def test_get_buffered_report_returns_none_on_error(enable_cache, mock_redis):
    mock_redis.hgetall.side_effect = RuntimeError("boom")
    assert await cache.get_buffered_report("e", "u") is None


# ---------------------------------------------------------------------------
# drain_event_buffer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drain_returns_zero_when_directory_empty(enable_cache, mock_redis):
    mock_redis.smembers.return_value = set()
    assert await cache.drain_event_buffer("e1") == 0
    # Should not attempt a batch UPDATE.
    mock_redis.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_drain_handles_redis_error_gracefully(enable_cache, mock_redis):
    mock_redis.smembers.side_effect = RuntimeError("boom")
    assert await cache.drain_event_buffer("e1") == 0


@pytest.mark.asyncio
async def test_drain_batch_updates_then_clears_buffer(enable_cache, mock_redis, monkeypatch):
    """End-to-end success path: smembers returns users → pipeline reads hashes →
    _batch_update_db is called → per-user buf keys cleared → stats cache invalidated.
    """
    mock_redis.smembers.return_value = {"u1", "u2"}
    pipe = mock_redis.pipeline.return_value
    pipe.execute.side_effect = [
        # First execute(): reading hashes for u1, u2.
        [
            {"status": "safe", "message": "", "reported_at": "2026-01-01T00:00:00+00:00"},
            {"status": "need_help", "message": "stuck", "reported_at": "2026-01-01T00:00:01+00:00"},
        ],
        # Second execute(): batch-delete the per-user keys.
        [None, None],
    ]

    fake_batch = AsyncMock(return_value=2)
    monkeypatch.setattr(cache, "_batch_update_db", fake_batch)
    fake_invalidate = AsyncMock()
    monkeypatch.setattr(cache, "cache_invalidate_pattern", fake_invalidate)

    n = await cache.drain_event_buffer("evt-1")
    assert n == 2
    fake_batch.assert_awaited_once()
    fake_invalidate.assert_awaited_once_with("stats:event:evt-1:*")
    # Directory key should have been deleted before reading hashes.
    mock_redis.delete.assert_any_await("buf:events_with_pending:evt-1")


@pytest.mark.asyncio
async def test_drain_skips_when_all_records_missing_status(enable_cache, mock_redis, monkeypatch):
    mock_redis.smembers.return_value = {"u1"}
    pipe = mock_redis.pipeline.return_value
    pipe.execute.return_value = [{}]  # hash with no status

    fake_batch = AsyncMock()
    monkeypatch.setattr(cache, "_batch_update_db", fake_batch)

    n = await cache.drain_event_buffer("evt-1")
    assert n == 0
    fake_batch.assert_not_awaited()
