"""Integration tests for reminder endpoints."""
import pytest


@pytest.mark.integration
class TestTriggerReminders:
    async def test_all_unreported_users_get_reminded(
        self, client, manager_headers, active_event
    ):
        r = await client.post(
            f"/api/events/{active_event.id}/remind", headers=manager_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["reminded_count"] == 3
        assert "3" in data["message"]

    async def test_excludes_already_reported_users(
        self, client, manager_headers, employee_headers, active_event
    ):
        event_id = str(active_event.id)
        # Employee reports first
        await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        r = await client.post(
            f"/api/events/{event_id}/remind", headers=manager_headers
        )
        assert r.json()["reminded_count"] == 2  # admin + manager still unreported

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

    async def test_admin_can_trigger_reminders(self, client, admin_headers, active_event):
        r = await client.post(
            f"/api/events/{active_event.id}/remind", headers=admin_headers
        )
        assert r.status_code == 200

    async def test_employee_cannot_trigger_reminders(
        self, client, employee_headers, active_event
    ):
        r = await client.post(
            f"/api/events/{active_event.id}/remind", headers=employee_headers
        )
        assert r.status_code == 403


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
        assert len(reminders) == 3
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
