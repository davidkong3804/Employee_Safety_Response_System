import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status

from app.modules.users.models import User
from app.rate_limiter import RedisRateLimiter


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        employee_id="E123",
        name="Test Employee",
        email="test@tsmc.com",
        role="employee",
        phone="0912-345-678",
        is_active=True,
    )


@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    return req


class TestRedisRateLimiter:
    @patch("app.rate_limiter._DISABLED", True)
    async def test_disabled_rate_limiter_allows_request(self, mock_request, mock_user):
        limiter = RedisRateLimiter(limit=5, window=10, action="test")
        result = await limiter(mock_request, current_user=mock_user)
        assert result is None

    @patch("app.rate_limiter._DISABLED", False)
    @patch("app.rate_limiter._get_client")
    async def test_under_limit_allows_request(self, mock_get_client, mock_request, mock_user):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 1, 3, True])
        mock_redis.pipeline.return_value = mock_pipeline
        mock_get_client.return_value = mock_redis

        limiter = RedisRateLimiter(limit=5, window=10, action="test")
        result = await limiter(mock_request, current_user=mock_user)
        assert result is None

        mock_pipeline.zremrangebyscore.assert_called_once()
        mock_pipeline.zadd.assert_called_once()
        mock_pipeline.zcard.assert_called_once()
        mock_pipeline.expire.assert_called_once()

    @patch("app.rate_limiter._DISABLED", False)
    @patch("app.rate_limiter._get_client")
    async def test_over_limit_raises_429(self, mock_get_client, mock_request, mock_user):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 1, 6, True])  # card_count is 6 > limit 5
        mock_redis.pipeline.return_value = mock_pipeline

        # Return oldest timestamp with score
        mock_redis.zrange = AsyncMock(return_value=[("some_time", 1000.0)])
        mock_get_client.return_value = mock_redis

        limiter = RedisRateLimiter(limit=5, window=10, action="test")

        with pytest.raises(HTTPException) as exc_info:
            with patch("time.time", return_value=1005.0):  # 1000 oldest, 10 window -> retry after 5
                await limiter(mock_request, current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc_info.value.detail == "Too many requests. Please try again later."
        assert exc_info.value.headers["Retry-After"] == "5"

    @patch("app.rate_limiter._DISABLED", False)
    @patch("app.rate_limiter._get_client")
    async def test_redis_error_gracefully_degrades(self, mock_get_client, mock_request, mock_user):
        mock_get_client.side_effect = Exception("Redis connection refused")

        limiter = RedisRateLimiter(limit=5, window=10, action="test")
        result = await limiter(mock_request, current_user=mock_user)
        assert result is None
