"""Integration tests for /api/events – core business logic."""
import pytest
from sqlalchemy import select

from app.modules.notifications.models import Reminder
from app.modules.reports.models import SafetyReport


@pytest.mark.integration
class TestListEvents:
    async def test_returns_200_without_auth(self, client):
        r = await client.get("/api/events")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_active_events_come_before_closed(self, client, active_event, admin_headers, db_session):
        from app.modules.events.models import Event
        from datetime import datetime, timezone

        # Create a closed event
        closed = Event(
            title="Closed Event",
            event_type="fire",
            severity="low",
            status="closed",
            created_by=active_event.created_by,
            closed_at=datetime.now(timezone.utc),
        )
        db_session.add(closed)
        await db_session.flush()

        r = await client.get("/api/events")
        events = r.json()
        statuses = [e["status"] for e in events]
        active_indices = [i for i, s in enumerate(statuses) if s == "active"]
        closed_indices = [i for i, s in enumerate(statuses) if s == "closed"]
        assert max(active_indices) < min(closed_indices)


@pytest.mark.integration
class TestGetEvent:
    async def test_returns_event_by_id(self, client, active_event):
        r = await client.get(f"/api/events/{active_event.id}")
        assert r.status_code == 200
        assert r.json()["title"] == "Test Earthquake Event"

    async def test_nonexistent_event_returns_404(self, client):
        r = await client.get("/api/events/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


@pytest.mark.integration
class TestCreateEvent:
    async def test_admin_creates_event_returns_201(self, client, admin_headers, admin_user):
        r = await client.post(
            "/api/events",
            json={"title": "New Quake", "event_type": "earthquake", "severity": "high"},
            headers=admin_headers,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "New Quake"
        assert data["status"] == "active"
        assert data["closed_at"] is None

    async def test_create_event_generates_report_for_every_active_user(
        self, client, admin_headers, admin_user, manager_user, employee_user, db_session
    ):
        r = await client.post(
            "/api/events",
            json={"title": "Report Gen Test", "event_type": "fire", "severity": "medium"},
            headers=admin_headers,
        )
        assert r.status_code == 201
        event_id = r.json()["id"]

        result = await db_session.execute(
            select(SafetyReport).where(SafetyReport.event_id == event_id)
        )
        reports = result.scalars().all()
        assert len(reports) == 3  # admin + manager + employee
        assert all(rep.status is None for rep in reports)

    async def test_inactive_user_excluded_from_auto_reports(
        self, client, admin_headers, admin_user, manager_user, employee_user, db_session
    ):
        employee_user.is_active = False
        await db_session.flush()

        r = await client.post(
            "/api/events",
            json={"title": "Inactive Test", "event_type": "other", "severity": "low"},
            headers=admin_headers,
        )
        event_id = r.json()["id"]

        result = await db_session.execute(
            select(SafetyReport).where(SafetyReport.event_id == event_id)
        )
        reports = result.scalars().all()
        assert len(reports) == 2  # admin + manager only

    async def test_manager_cannot_create_event(self, client, manager_headers):
        r = await client.post(
            "/api/events",
            json={"title": "Unauth", "event_type": "earthquake", "severity": "low"},
            headers=manager_headers,
        )
        assert r.status_code == 403

    async def test_employee_cannot_create_event(self, client, employee_headers):
        r = await client.post(
            "/api/events",
            json={"title": "Unauth", "event_type": "earthquake", "severity": "low"},
            headers=employee_headers,
        )
        assert r.status_code == 403

    async def test_unauthenticated_cannot_create_event(self, client):
        r = await client.post(
            "/api/events",
            json={"title": "Unauth", "event_type": "earthquake", "severity": "low"},
        )
        assert r.status_code == 401


@pytest.mark.integration
class TestUpdateEvent:
    async def test_admin_can_update_title(self, client, admin_headers, active_event):
        r = await client.patch(
            f"/api/events/{active_event.id}",
            json={"title": "Updated Title"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Updated Title"

    async def test_closing_event_sets_closed_at(self, client, admin_headers, active_event):
        r = await client.patch(
            f"/api/events/{active_event.id}",
            json={"status": "closed"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "closed"
        assert data["closed_at"] is not None

    async def test_update_nonexistent_event_returns_404(self, client, admin_headers):
        r = await client.patch(
            "/api/events/00000000-0000-0000-0000-000000000000",
            json={"title": "Ghost"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_manager_cannot_update_event(self, client, manager_headers, active_event):
        r = await client.patch(
            f"/api/events/{active_event.id}",
            json={"title": "Hacked"},
            headers=manager_headers,
        )
        assert r.status_code == 403


@pytest.mark.integration
class TestDeleteEvent:
    async def test_admin_can_delete_event(self, client, admin_headers, active_event):
        event_id = str(active_event.id)
        r = await client.delete(f"/api/events/{event_id}", headers=admin_headers)
        assert r.status_code == 204

        r2 = await client.get(f"/api/events/{event_id}")
        assert r2.status_code == 404

    async def test_delete_cascades_reports_and_reminders(
        self, client, admin_headers, active_event, db_session
    ):
        event_id = active_event.id
        # Trigger a reminder to create a reminder record
        await client.post(f"/api/events/{event_id}/remind", headers=admin_headers)

        await client.delete(f"/api/events/{event_id}", headers=admin_headers)

        reports = await db_session.execute(
            select(SafetyReport).where(SafetyReport.event_id == event_id)
        )
        assert reports.scalars().all() == []

        reminders = await db_session.execute(
            select(Reminder).where(Reminder.event_id == event_id)
        )
        assert reminders.scalars().all() == []

    async def test_delete_nonexistent_event_returns_404(self, client, admin_headers):
        r = await client.delete(
            "/api/events/00000000-0000-0000-0000-000000000000",
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_employee_cannot_delete_event(self, client, employee_headers, active_event):
        r = await client.delete(
            f"/api/events/{active_event.id}", headers=employee_headers
        )
        assert r.status_code == 403
