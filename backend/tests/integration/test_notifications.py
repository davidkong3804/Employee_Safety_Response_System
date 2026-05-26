"""Integration tests for reminder endpoints."""
import pytest

from app.modules.reports.models import SafetyReport
from app.modules.users.models import User


@pytest.mark.integration
class TestTriggerReminders:
    async def test_manager_reminds_own_department_unreported(
        self, client, manager_headers, active_event
    ):
        # Manager (Engineering) reminds Engineering's unreported users only:
        # manager + employee. Admin (IT) must NOT be reminded by this call.
        r = await client.post(
            f"/api/events/{active_event.id}/remind", headers=manager_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["reminded_count"] == 2
        assert "2" in data["message"]

    async def test_excludes_already_reported_users(
        self, client, manager_headers, employee_headers, active_event
    ):
        event_id = str(active_event.id)
        # Employee (Engineering) reports first
        await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        r = await client.post(
            f"/api/events/{event_id}/remind", headers=manager_headers
        )
        # Engineering scope minus already-reported employee → only manager left.
        assert r.json()["reminded_count"] == 1

    async def test_reminder_count_increments_on_repeat(
        self, client, manager_headers, active_event
    ):
        event_id = str(active_event.id)
        await client.post(f"/api/events/{event_id}/remind", headers=manager_headers)
        await client.post(f"/api/events/{event_id}/remind", headers=manager_headers)

        r = await client.get(f"/api/events/{event_id}/reminders", headers=manager_headers)
        reminders = r.json()
        assert len(reminders) > 0
        assert all(rem["reminder_count"] == 2 for rem in reminders)

    async def test_admin_reminds_across_all_departments(
        self, client, admin_headers, active_event
    ):
        # Admin sees the whole event — IT (admin) + Engineering (manager,
        # employee) → 3. Confirms admin is not narrowed by the manager
        # dept-scope rule.
        r = await client.post(
            f"/api/events/{active_event.id}/remind", headers=admin_headers
        )
        assert r.status_code == 200
        assert r.json()["reminded_count"] == 3

    async def test_employee_cannot_trigger_reminders(
        self, client, employee_headers, active_event
    ):
        r = await client.post(
            f"/api/events/{active_event.id}/remind", headers=employee_headers
        )
        assert r.status_code == 403

    async def test_excludes_inactive_users(
        self, client, manager_headers, active_event, db_session
    ):
        """Placeholder rows for is_active=False users must not be reminded.

        Real-world trigger: load-test accounts were deactivated (or pruned
        from the users table) but their placeholder SafetyReport rows
        remain because deletion was scoped narrowly. The remind query
        must JOIN users + filter is_active=True to skip them.
        """
        ghost = User(
            employee_id="TEST_GHOST",
            name="Inactive Ghost",
            email="ghost@example.com",
            password_hash="x",
            role="employee",
            department="Engineering",
            facility="TestFab",
            is_active=False,
        )
        db_session.add(ghost)
        await db_session.flush()
        db_session.add(SafetyReport(event_id=active_event.id, user_id=ghost.id))
        await db_session.flush()

        r = await client.post(
            f"/api/events/{active_event.id}/remind", headers=manager_headers
        )
        # Engineering scope = manager + employee = 2. Ghost (also Engineering
        # but inactive) must be excluded by the User.is_active filter.
        assert r.json()["reminded_count"] == 2


@pytest.mark.integration
class TestGetReminders:
    async def test_empty_before_any_reminder_triggered(
        self, client, manager_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/reminders", headers=manager_headers
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_returns_reminders_after_trigger(
        self, client, manager_headers, active_event
    ):
        event_id = str(active_event.id)
        await client.post(f"/api/events/{event_id}/remind", headers=manager_headers)

        r = await client.get(f"/api/events/{event_id}/reminders", headers=manager_headers)
        reminders = r.json()
        # Manager triggered → only Engineering scope persisted (manager + employee).
        assert len(reminders) == 2
        for rem in reminders:
            assert rem["reminder_count"] == 1
            assert rem["last_reminded"] is not None

    async def test_employee_cannot_get_reminders(
        self, client, employee_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/reminders", headers=employee_headers
        )
        assert r.status_code == 403
