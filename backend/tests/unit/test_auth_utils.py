"""Unit tests for auth utility functions – no database required."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt

from app.config import settings
from app.modules.auth.router import create_access_token, hash_password, verify_password


class TestHashPassword:
    def test_returns_bcrypt_format(self):
        hashed = hash_password("password123")
        assert hashed.startswith("$2b$")

    def test_different_salt_each_call(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_long_password(self):
        hashed = hash_password("a" * 72)
        assert hashed.startswith("$2b$")


class TestVerifyPassword:
    # verify_password is now async (offloads bcrypt to a thread pool so it
    # doesn't block the event loop). pytest.ini has `asyncio_mode = auto`
    # so `async def test_...` is auto-collected as an asyncio test.
    async def test_correct_password_returns_true(self):
        hashed = hash_password("secret")
        assert await verify_password("secret", hashed) is True

    async def test_wrong_password_returns_false(self):
        hashed = hash_password("secret")
        assert await verify_password("wrong", hashed) is False

    async def test_empty_password_wrong_returns_false(self):
        hashed = hash_password("secret")
        assert await verify_password("", hashed) is False


class TestCreateAccessToken:
    def test_token_contains_sub(self):
        token = create_access_token("some-uuid")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == "some-uuid"

    def test_token_has_exp(self):
        token = create_access_token("uid")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert "exp" in payload
        assert payload["exp"] > datetime.now(timezone.utc).timestamp()

    def test_token_expires_after_configured_minutes(self):
        before = datetime.now(timezone.utc)
        token = create_access_token("uid")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        # Should expire roughly JWT_EXPIRE_MINUTES from now (allow 5s slack)
        expected = before + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        assert abs((exp - expected).total_seconds()) < 5

    def test_expired_token_raises_jwt_error(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = jwt.encode(
            {"sub": "uid", "exp": past},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(JWTError):
            jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

    def test_tampered_token_raises_jwt_error(self):
        token = create_access_token("uid") + "tampered"
        with pytest.raises(JWTError):
            jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
