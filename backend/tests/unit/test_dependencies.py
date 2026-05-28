"""Unit tests for require_role dependency – no database required."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.dependencies import require_role
from app.modules.users.models import User


def _mock_user(role: str) -> User:
    user = MagicMock(spec=User)
    user.role = role
    return user


class TestRequireRole:
    async def test_allows_matching_role(self):
        checker = require_role("admin")
        user = _mock_user("admin")
        result = await checker(current_user=user)
        assert result is user

    async def test_allows_any_of_multiple_roles(self):
        checker = require_role("manager", "admin")
        manager = _mock_user("manager")
        result = await checker(current_user=manager)
        assert result is manager

    async def test_raises_403_for_wrong_role(self):
        checker = require_role("admin")
        user = _mock_user("employee")
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Insufficient permissions"

    async def test_employee_blocked_from_admin_and_manager(self):
        checker = require_role("admin", "manager")
        user = _mock_user("employee")
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)
        assert exc_info.value.status_code == 403

    async def test_returns_the_user_object(self):
        checker = require_role("admin", "manager", "employee")
        user = _mock_user("employee")
        result = await checker(current_user=user)
        assert result is user
