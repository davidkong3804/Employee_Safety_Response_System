"""Integration tests for /api/users endpoints."""
import pytest


@pytest.mark.integration
class TestListUsers:
    async def test_admin_can_list_users(self, client, admin_headers, admin_user, manager_user, employee_user):
        r = await client.get("/api/users", headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 3

    async def test_manager_can_list_users(self, client, manager_headers, manager_user, employee_user):
        r = await client.get("/api/users", headers=manager_headers)
        assert r.status_code == 200

    async def test_employee_cannot_list_users(self, client, employee_headers):
        r = await client.get("/api/users", headers=employee_headers)
        assert r.status_code == 403

    async def test_filter_by_role(self, client, admin_headers, admin_user, manager_user, employee_user):
        r = await client.get("/api/users?role=manager", headers=admin_headers)
        assert r.status_code == 200
        users = r.json()
        assert all(u["role"] == "manager" for u in users)

    async def test_filter_by_facility(self, client, admin_headers, admin_user, manager_user):
        r = await client.get("/api/users?facility=TestFab", headers=admin_headers)
        assert r.status_code == 200
        users = r.json()
        assert all(u["facility"] == "TestFab" for u in users)


@pytest.mark.integration
class TestCreateUser:
    async def test_admin_creates_user_returns_201(self, client, admin_headers):
        r = await client.post(
            "/api/users",
            json={
                "employee_id": "NEW001",
                "name": "New User",
                "email": "new@example.com",
                "password": "password",
                "role": "employee",
                "department": "Engineering",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["employee_id"] == "NEW001"
        assert data["is_active"] is True
        assert "password" not in data

    async def test_manager_cannot_create_user(self, client, manager_headers):
        r = await client.post(
            "/api/users",
            json={
                "employee_id": "UNAUTH",
                "name": "X",
                "email": "x@example.com",
                "password": "pw",
                "role": "employee",
            },
            headers=manager_headers,
        )
        assert r.status_code == 403

    async def test_duplicate_employee_id_fails(self, client, admin_headers, employee_user):
        r = await client.post(
            "/api/users",
            json={
                "employee_id": "TEST_E001",  # already exists
                "name": "Duplicate",
                "email": "unique_dup@example.com",
                "password": "pw",
                "role": "employee",
            },
            headers=admin_headers,
        )
        assert r.status_code == 409

    async def test_missing_required_field_returns_422(self, client, admin_headers):
        r = await client.post(
            "/api/users",
            json={"employee_id": "X", "name": "X"},
            headers=admin_headers,
        )
        assert r.status_code == 422


@pytest.mark.integration
class TestUpdateUser:
    async def test_admin_updates_user_role(self, client, admin_headers, employee_user):
        r = await client.patch(
            f"/api/users/{employee_user.id}",
            json={"role": "manager"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["role"] == "manager"

    async def test_admin_updates_user_name(self, client, admin_headers, employee_user):
        r = await client.patch(
            f"/api/users/{employee_user.id}",
            json={"name": "New Name"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"

    async def test_update_nonexistent_user_returns_404(self, client, admin_headers):
        r = await client.patch(
            "/api/users/00000000-0000-0000-0000-000000000000",
            json={"name": "Ghost"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_manager_cannot_update_user(self, client, manager_headers, employee_user):
        r = await client.patch(
            f"/api/users/{employee_user.id}",
            json={"name": "Hacked"},
            headers=manager_headers,
        )
        assert r.status_code == 403


@pytest.mark.integration
class TestDeleteUser:
    async def test_admin_soft_deletes_user(self, client, admin_headers, employee_user):
        user_id = str(employee_user.id)
        r = await client.delete(f"/api/users/{user_id}", headers=admin_headers)
        assert r.status_code == 204

        # User still exists but is_active=False
        r2 = await client.get("/api/users", headers=admin_headers)
        matching = [u for u in r2.json() if u["id"] == user_id]
        assert len(matching) == 1
        assert matching[0]["is_active"] is False

    async def test_delete_nonexistent_user_returns_404(self, client, admin_headers):
        r = await client.delete(
            "/api/users/00000000-0000-0000-0000-000000000000",
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_employee_cannot_delete_user(self, client, employee_headers, admin_user):
        r = await client.delete(f"/api/users/{admin_user.id}", headers=employee_headers)
        assert r.status_code == 403
