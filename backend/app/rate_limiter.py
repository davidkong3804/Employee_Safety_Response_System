import logging
import time

from fastapi import Depends, HTTPException, Request, status

from app.cache import _DISABLED, _get_client
from app.dependencies import get_current_user
from app.modules.users.models import User

log = logging.getLogger(__name__)


class RedisRateLimiter:
    """FastAPI dependency for sliding-window rate limiting backed by Redis.

    Limits are applied per authenticated user. If Redis is unavailable or
    caching is disabled, rate limiting degrades gracefully to allow all requests.
    """

    def __init__(self, limit: int, window: int, action: str):
        self.limit = limit
        self.window = window
        self.action = action

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
    ):
        if _DISABLED:
            return

        identifier = str(current_user.id)
        key = f"rate_limit:{self.action}:{identifier}"
        now = time.time()
        clear_before = now - self.window

        try:
            client = _get_client()
            pipe = client.pipeline()
            # 1. Prune expired logs outside the sliding window
            pipe.zremrangebyscore(key, 0, clear_before)
            # 2. Add current request log
            pipe.zadd(key, mapping={str(now): now})
            # 3. Count total logs in this window
            pipe.zcard(key)
            # 4. Refresh key TTL so it cleans up when idle
            pipe.expire(key, self.window)

            # Execute transactional pipeline
            results = await pipe.execute()
            card_count = results[2]

            if card_count > self.limit:
                # Find retry duration dynamically based on the oldest element
                oldest_elements = await client.zrange(key, 0, 0, withscores=True)
                retry_after = self.window
                if oldest_elements:
                    oldest_score = oldest_elements[0][1]
                    retry_after = max(1, int(oldest_score + self.window - now))

                log.warning(
                    "Rate limit exceeded for user %s on action %s: count=%s limit=%s. Blocked for %s s.",
                    identifier,
                    self.action,
                    card_count,
                    self.limit,
                    retry_after,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

        except HTTPException:
            raise
        except Exception as exc:
            # Graceful degradation: Redis down should never block critical safety reporting
            log.warning(
                "Rate limiter degraded for user %s on action %s: %s",
                identifier,
                self.action,
                exc,
            )
            return
