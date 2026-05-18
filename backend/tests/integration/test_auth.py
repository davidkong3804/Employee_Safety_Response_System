"""Integration tests for /api/auth/* endpoints."""
import pytest


@pytest.mark.integration
class TestLogin:
    async def test_valid_credentials_returns_token(self, client, employee_user):
        r = await client.post(
            "/api/auth/login",
            json={"employee_id": "TEST_E001", "password": "testpassword"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_wrong_password_returns_401(self, client, employee_user):
        r = await client.post(
            "/api/auth/login",
            json={"employee_id": "TEST_E001", "password": "wrongpassword"},
        )
        assert r.status_code == 401
        assert "Incorrect" in r.json()["detail"]

    async def test_nonexistent_user_returns_401(self, client):
        r = await client.post(
            "/api/auth/login",
            json={"employee_id": "NOBODY", "password": "anything"},
        )
        assert r.status_code == 401

    async def test_missing_fields_returns_422(self, client):
        r = await client.post("/api/auth/login", json={"employee_id": "E001"})
        assert r.status_code == 422

    async def test_inactive_user_cannot_login(self, client, employee_user, db_session):
        employee_user.is_active = False
        await db_session.flush()
        r = await client.post(
            "/api/auth/login",
            json={"employee_id": "TEST_E001", "password": "testpassword"},
        )
        assert r.status_code == 401


@pytest.mark.integration
class TestGetMe:
    async def test_returns_current_user_profile(self, client, employee_user, employee_headers):
        r = await client.get("/api/auth/me", headers=employee_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["employee_id"] == "TEST_E001"
        assert data["role"] == "employee"
        assert data["name"] == "Test Employee"

    async def test_no_token_returns_401(self, client):
        r = await client.get("/api/auth/me")
        assert r.status_code == 401

    async def test_invalid_token_returns_401(self, client):
        r = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        assert r.status_code == 401

    async def test_admin_profile_has_admin_role(self, client, admin_user, admin_headers):
        r = await client.get("/api/auth/me", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
