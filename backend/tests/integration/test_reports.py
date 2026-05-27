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

    async def test_invalid_status_returns_422(self, client, employee_headers, active_event):
        r = await client.post(
            f"/api/events/{str(active_event.id)}/report",
            json={"status": "unknown_status"},
            headers=employee_headers,
        )
        assert r.status_code == 422

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
    async def test_returns_placeholder_before_submission(self, client, employee_headers, active_event):
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
    async def test_admin_sees_event_wide_totals(self, client, admin_headers, active_event):
        r = await client.get(f"/api/events/{active_event.id}/stats", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        # Admin sees all 3 placeholders (admin + manager + employee).
        assert data["total"] == 3
        assert data["unreported"] == 3
        assert data["report_rate"] == 0.0

    async def test_manager_stats_scoped_to_own_department(self, client, manager_headers, active_event):
        r = await client.get(f"/api/events/{active_event.id}/stats", headers=manager_headers)
        assert r.status_code == 200
        data = r.json()
        # Manager is in Engineering — sees only Engineering placeholders
        # (manager + employee), NOT the admin (who is in IT).
        assert data["total"] == 2
        assert data["unreported"] == 2

    async def test_stats_after_one_safe_report_admin_view(self, client, admin_headers, employee_headers, active_event):
        event_id = str(active_event.id)
        await client.post(
            f"/api/events/{event_id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        r = await client.get(f"/api/events/{event_id}/stats", headers=admin_headers)
        data = r.json()
        # 1 safe out of 3 total.
        assert data["safe"] == 1
        assert data["unreported"] == 2
        assert data["report_rate"] == pytest.approx(33.3, abs=0.1)

    async def test_stats_after_one_safe_report_manager_view(
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
        # Manager-scoped: 1 safe out of 2 Engineering rows (manager + employee).
        assert data["safe"] == 1
        assert data["unreported"] == 1
        assert data["report_rate"] == pytest.approx(50.0, abs=0.1)

    async def test_employee_cannot_see_stats(self, client, employee_headers, active_event):
        r = await client.get(f"/api/events/{active_event.id}/stats", headers=employee_headers)
        assert r.status_code == 403


@pytest.mark.integration
class TestStatsByDepartment:
    async def test_admin_sees_all_departments(self, client, admin_headers, active_event):
        r = await client.get(f"/api/events/{active_event.id}/stats/by-department", headers=admin_headers)
        assert r.status_code == 200
        dept_names = {d["department"] for d in r.json()}
        assert "Engineering" in dept_names
        assert "IT" in dept_names

    async def test_manager_dept_stats_only_own_department(self, client, manager_headers, active_event):
        r = await client.get(
            f"/api/events/{active_event.id}/stats/by-department",
            headers=manager_headers,
        )
        assert r.status_code == 200
        data = r.json()
        # Manager only sees their own dept on the chart — no cross-dept leak.
        assert {d["department"] for d in data} == {"Engineering"}
        eng = next(d for d in data if d["department"] == "Engineering")
        assert eng["total"] == 2  # manager + employee, not admin

    async def test_employee_cannot_see_department_stats(self, client, employee_headers, active_event):
        r = await client.get(
            f"/api/events/{active_event.id}/stats/by-department",
            headers=employee_headers,
        )
        assert r.status_code == 403


@pytest.mark.integration
class TestTeamStatus:
    async def test_admin_sees_all_reports(self, client, admin_headers, active_event):
        r = await client.get(f"/api/events/{active_event.id}/team-status", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_manager_sees_own_department_employees(
        self, client, manager_headers, manager_user, employee_user, admin_user, active_event
    ):
        r = await client.get(f"/api/events/{active_event.id}/team-status", headers=manager_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        user_ids = {rep["user_id"] for rep in items}
        assert str(manager_user.id) in user_ids  # self
        assert str(employee_user.id) in user_ids  # same dept (Engineering)
        assert str(admin_user.id) not in user_ids  # different dept (IT)

    async def test_manager_sees_dept_employee_even_if_not_direct_report(
        self, client, manager_headers, manager_user, admin_user, db_session, active_event
    ):
        # Engineering employee whose manager is the ADMIN, not manager_user.
        # Old behaviour (manager_id_snapshot scope) would have hidden them;
        # new dept-scope must show them.
        from app.modules.auth.router import hash_password as _hash
        from app.modules.reports.models import SafetyReport
        from app.modules.users.models import User

        other = User(
            employee_id="TEST_E_OTHER_BOSS",
            name="Other Boss Engineer",
            email="other.boss@example.com",
            password_hash=_hash("testpassword"),
            role="employee",
            department="Engineering",
            facility="TestFab",
            manager_id=admin_user.id,  # not manager_user
            is_active=True,
        )
        db_session.add(other)
        await db_session.flush()
        db_session.add(
            SafetyReport(
                event_id=active_event.id,
                user_id=other.id,
                manager_id_snapshot=other.manager_id,
                department_snapshot=other.department,
                facility_snapshot=other.facility,
            )
        )
        await db_session.flush()

        r = await client.get(f"/api/events/{active_event.id}/team-status", headers=manager_headers)
        ids = {rep["user_id"] for rep in r.json()["items"]}
        assert str(other.id) in ids

    async def test_manager_does_not_see_other_departments(
        self, client, manager_headers, manager_user, db_session, active_event
    ):
        from app.modules.auth.router import hash_password as _hash
        from app.modules.reports.models import SafetyReport
        from app.modules.users.models import User

        # Same manager_id as manager_user — but different department. Scope
        # is dept-based now, so this row must be excluded.
        other = User(
            employee_id="TEST_E_SALES",
            name="Sales Person",
            email="sales@example.com",
            password_hash=_hash("testpassword"),
            role="employee",
            department="Sales",
            facility="TestFab",
            manager_id=manager_user.id,
            is_active=True,
        )
        db_session.add(other)
        await db_session.flush()
        db_session.add(
            SafetyReport(
                event_id=active_event.id,
                user_id=other.id,
                manager_id_snapshot=other.manager_id,
                department_snapshot=other.department,  # "Sales"
                facility_snapshot=other.facility,
            )
        )
        await db_session.flush()

        r = await client.get(f"/api/events/{active_event.id}/team-status", headers=manager_headers)
        ids = {rep["user_id"] for rep in r.json()["items"]}
        assert str(other.id) not in ids

    async def test_pagination_returns_correct_slice_and_total(
        self, client, admin_headers, manager_user, db_session, active_event
    ):
        from sqlalchemy import select as _select

        from app.modules.auth.router import hash_password as _hash
        from app.modules.reports.models import SafetyReport
        from app.modules.users.models import User

        # 3 existing + 100 bulk = 103 placeholders for this event
        for i in range(100):
            db_session.add(
                User(
                    employee_id=f"TEST_E_BULK_{i:03d}",
                    name=f"Bulk Employee {i:03d}",
                    email=f"bulk{i:03d}@example.com",
                    password_hash=_hash("testpassword"),
                    role="employee",
                    department="Engineering",
                    facility="TestFab",
                    manager_id=manager_user.id,
                    is_active=True,
                )
            )
        await db_session.flush()
        bulk_users = (
            (await db_session.execute(_select(User).where(User.employee_id.like("TEST_E_BULK_%")))).scalars().all()
        )
        for u in bulk_users:
            db_session.add(
                SafetyReport(
                    event_id=active_event.id,
                    user_id=u.id,
                    manager_id_snapshot=u.manager_id,
                    department_snapshot=u.department,
                    facility_snapshot=u.facility,
                )
            )
        await db_session.flush()

        # First page
        r = await client.get(
            f"/api/events/{active_event.id}/team-status?limit=40&offset=0",
            headers=admin_headers,
        )
        data = r.json()
        assert data["total"] == 103
        assert data["limit"] == 40
        assert data["offset"] == 0
        assert len(data["items"]) == 40

        # Last partial page: 103 - 80 = 23 rows
        r = await client.get(
            f"/api/events/{active_event.id}/team-status?limit=40&offset=80",
            headers=admin_headers,
        )
        data = r.json()
        assert data["total"] == 103
        assert len(data["items"]) == 23

    async def test_status_filter_unreported_excludes_submitted(
        self, client, admin_headers, employee_headers, active_event
    ):
        await client.post(
            f"/api/events/{active_event.id}/report",
            json={"status": "safe"},
            headers=employee_headers,
        )
        r = await client.get(
            f"/api/events/{active_event.id}/team-status?status=unreported",
            headers=admin_headers,
        )
        data = r.json()
        # admin + manager remain unreported; employee submitted safe
        assert data["total"] == 2
        statuses = {item["status"] for item in data["items"]}
        assert statuses == {None}

    async def test_search_filters_by_employee_id(self, client, admin_headers, employee_user, active_event):
        r = await client.get(
            f"/api/events/{active_event.id}/team-status?search=TEST_E001",
            headers=admin_headers,
        )
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["employee_id"] == "TEST_E001"

    async def test_employee_cannot_see_team_status(self, client, employee_headers, active_event):
        r = await client.get(f"/api/events/{active_event.id}/team-status", headers=employee_headers)
        assert r.status_code == 403


@pytest.mark.integration
class TestAllStatus:
    async def test_admin_gets_all_reports(self, client, admin_headers, active_event):
        r = await client.get(f"/api/events/{active_event.id}/all-status", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 3
        assert len(r.json()["items"]) == 3

    async def test_filter_by_facility(self, client, admin_headers, active_event):
        r = await client.get(
            f"/api/events/{active_event.id}/all-status?facility=TestFab",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) == 3

    async def test_filter_by_unknown_facility_returns_empty(self, client, admin_headers, active_event):
        r = await client.get(
            f"/api/events/{active_event.id}/all-status?facility=NoSuchFab",
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_manager_cannot_see_all_status(self, client, manager_headers, active_event):
        r = await client.get(f"/api/events/{active_event.id}/all-status", headers=manager_headers)
        assert r.status_code == 403


@pytest.mark.integration
class TestOrgSnapshotIsolation:
    """C6: an org change *after* an event is created must not retroactively
    alter that event's report views — manager team-status, dept stats and
    facility filters all read from the snapshot, never the user's current
    org context.
    """

    async def test_team_status_stable_when_employee_changes_department(
        self,
        client,
        manager_headers,
        manager_user,
        employee_user,
        db_session,
        active_event,
    ):
        # Before any change: the employee shows up in the manager's view.
        r = await client.get(f"/api/events/{active_event.id}/team-status", headers=manager_headers)
        assert r.status_code == 200
        before_ids = {rep["user_id"] for rep in r.json()["items"]}
        assert str(employee_user.id) in before_ids

        # Move the employee out of Engineering — only their *live* department
        # changes; the placeholder's department_snapshot stays "Engineering".
        employee_user.department = "Sales"
        await db_session.flush()

        # Manager scope is dept-based, but it reads department_snapshot
        # (frozen), not live user.department — so the historical view is
        # unchanged.
        r = await client.get(f"/api/events/{active_event.id}/team-status", headers=manager_headers)
        assert r.status_code == 200
        after_ids = {rep["user_id"] for rep in r.json()["items"]}
        assert before_ids == after_ids
        assert str(employee_user.id) in after_ids

    async def test_dept_stats_stable_when_user_changes_department(
        self,
        client,
        admin_headers,
        admin_user,
        manager_user,
        employee_user,
        db_session,
        active_event,
    ):
        # Use admin's full-event view here: a manager's *own* dept change
        # legitimately shifts the manager's scope (their view follows them
        # to the new department by design), so the stability invariant —
        # historical snapshot data doesn't move — has to be checked from
        # an unscoped viewpoint.
        before = await client.get(
            f"/api/events/{active_event.id}/stats/by-department",
            headers=admin_headers,
        )
        assert before.status_code == 200
        before_depts = {d["department"]: d["total"] for d in before.json()}

        # Move every test user into a fictional department.
        admin_user.department = "MovedDept"
        manager_user.department = "MovedDept"
        employee_user.department = "MovedDept"
        await db_session.flush()

        # The historical event's dept stats should still match the snapshot,
        # not the new "MovedDept" assignment.
        after = await client.get(
            f"/api/events/{active_event.id}/stats/by-department",
            headers=admin_headers,
        )
        assert after.status_code == 200
        after_depts = {d["department"]: d["total"] for d in after.json()}
        assert after_depts == before_depts
        assert "MovedDept" not in after_depts

    async def test_all_status_facility_filter_uses_snapshot(
        self,
        client,
        admin_headers,
        employee_user,
        db_session,
        active_event,
    ):
        # active_event fixture pins facility=["TestFab"] and every test user
        # is on TestFab, so the filtered list should match the unfiltered one.
        r = await client.get(
            f"/api/events/{active_event.id}/all-status?facility=TestFab",
            headers=admin_headers,
        )
        before_count = len(r.json()["items"])
        assert before_count == 3

        # Move the employee to a different facility post-event.
        employee_user.facility = "OtherFab"
        await db_session.flush()

        # Snapshot-based filter must still return the same 3 records.
        r = await client.get(
            f"/api/events/{active_event.id}/all-status?facility=TestFab",
            headers=admin_headers,
        )
        assert len(r.json()["items"]) == before_count
        # And a filter on the new facility returns nothing — the snapshot
        # was TestFab, not OtherFab.
        r = await client.get(
            f"/api/events/{active_event.id}/all-status?facility=OtherFab",
            headers=admin_headers,
        )
        assert r.json()["items"] == []
