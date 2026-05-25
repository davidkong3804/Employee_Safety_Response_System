"""Integration tests for report submission and statistics endpoints."""
import pytest


@pytest.mark.integration
class TestSubmitReport:
    async def test_submit_safe_report(self, client, employee_headers, employee_user, active_event):
        event_id = str(active_event.id)
        r = await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "safe"
        assert data["user_id"] == str(employee_user.id)
        assert data["reported_at"] is not None

    async def test_submit_need_help_with_message(self, client, employee_headers, active_event):
        event_id = str(active_event.id)
        r = await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "need_help", "message": "Trapped in room B3"},
            headers=employee_headers,
        )
        assert r.status_code == 200
        assert r.json()["message"] == "Trapped in room B3"

    async def test_invalid_status_returns_400(self, client, employee_headers, active_event):
        r = await client.post(
            f"/api/events/{str(active_event.id)}/report",
            json={"status": "unknown_status"},
            headers=employee_headers,
        )
        assert r.status_code == 400

    async def test_no_placeholder_returns_404(self, client, admin_headers, employee_headers, employee_user, db_session):
        from uuid import UUID as PyUUID

        from sqlalchemy import delete as sa_delete

        from app.modules.reports.models import SafetyReport

        r_event = await client.post(
            "/api/events",
            json={"title": "No Placeholder Event", "event_type": "other", "severity": "low"},
            headers=admin_headers,
        )
        assert r_event.status_code == 201
        event_uuid = PyUUID(r_event.json()["id"])

        # Remove the employee's placeholder so no report record exists for them
        await db_session.execute(
            sa_delete(SafetyReport).where(
                SafetyReport.event_id == event_uuid,
                SafetyReport.user_id == employee_user.id,
            )
        )
        await db_session.flush()

        r = await client.post(
            f"/api/events/{event_uuid}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        assert r.status_code == 404

    async def test_resubmit_updates_existing_report(self, client, employee_headers, active_event):
        event_id = str(active_event.id)
        await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        r = await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "need_help", "message": "Changed"},
            headers=employee_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "need_help"

    async def test_unauthenticated_returns_401(self, client, active_event):
        r = await client.post(
            f"/api/events/{active_event.id}/report",
            json={"status": "safe"},
        )
        assert r.status_code == 401


@pytest.mark.integration
class TestGetMyReport:
    async def test_returns_placeholder_before_submission(
        self, client, employee_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/my-report",
            headers=employee_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] is None
        assert r.json()["reported_at"] is None

    async def test_returns_submitted_report(self, client, employee_headers, active_event):
        event_id = str(active_event.id)
        await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        r = await client.get(f"/api/events/{event_id}/my-report", headers=employee_headers)
        assert r.json()["status"] == "safe"


@pytest.mark.integration
class TestEventStats:
    async def test_initial_stats_all_unreported(
        self, client, manager_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/stats", headers=manager_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["safe"] == 0
        assert data["need_help"] == 0
        assert data["unreported"] == 3
        assert data["report_rate"] == 0.0

    async def test_stats_after_one_safe_report(
        self, client, manager_headers, employee_headers, active_event
    ):
        event_id = str(active_event.id)
        await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        r = await client.get(f"/api/events/{event_id}/stats", headers=manager_headers)
        data = r.json()
        assert data["safe"] == 1
        assert data["unreported"] == 2
        assert data["report_rate"] == pytest.approx(33.3, abs=0.1)

    async def test_employee_cannot_see_stats(self, client, employee_headers, active_event):
        r = await client.get(
            f"/api/events/{active_event.id}/stats", headers=employee_headers
        )
        assert r.status_code == 403


@pytest.mark.integration
class TestStatsByDepartment:
    async def test_groups_by_department(
        self, client, manager_headers, employee_headers, active_event
    ):
        event_id = str(active_event.id)
        await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        r = await client.get(
            f"/api/events/{event_id}/stats/by-department", headers=manager_headers
        )
        assert r.status_code == 200
        data = r.json()
        dept_names = {d["department"] for d in data}
        assert "Engineering" in dept_names  # manager + employee
        assert "IT" in dept_names  # admin

    async def test_employee_cannot_see_department_stats(
        self, client, employee_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/stats/by-department",
            headers=employee_headers,
        )
        assert r.status_code == 403


@pytest.mark.integration
class TestTeamStatus:
    async def test_admin_sees_all_reports(
        self, client, admin_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/team-status", headers=admin_headers
        )
        assert r.status_code == 200
        assert len(r.json()) == 3  # all 3 test users

    async def test_manager_sees_only_subordinates_and_self(
        self, client, manager_headers, manager_user, employee_user, admin_user, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/team-status", headers=manager_headers
        )
        assert r.status_code == 200
        reports = r.json()
        user_ids = {rep["user_id"] for rep in reports}
        assert str(manager_user.id) in user_ids
        assert str(employee_user.id) in user_ids
        assert str(admin_user.id) not in user_ids  # admin not under this manager

    async def test_employee_cannot_see_team_status(
        self, client, employee_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/team-status", headers=employee_headers
        )
        assert r.status_code == 403


@pytest.mark.integration
class TestAllStatus:
    async def test_admin_gets_all_reports(self, client, admin_headers, active_event):
        r = await client.get(
            f"/api/events/{active_event.id}/all-status", headers=admin_headers
        )
        assert r.status_code == 200
        assert len(r.json()) == 3

    async def test_filter_by_facility(self, client, admin_headers, active_event):
        r = await client.get(
            f"/api/events/{active_event.id}/all-status?facility=TestFab",
            headers=admin_headers,
        )
        assert r.status_code == 200
        # All 3 test users have facility=TestFab
        assert len(r.json()) == 3

    async def test_filter_by_unknown_facility_returns_empty(
        self, client, admin_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/all-status?facility=NoSuchFab",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_manager_cannot_see_all_status(
        self, client, manager_headers, active_event
    ):
        r = await client.get(
            f"/api/events/{active_event.id}/all-status", headers=manager_headers
        )
        assert r.status_code == 403
