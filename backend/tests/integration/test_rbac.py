"""Systematic RBAC matrix tests for all protected endpoints.

403 is checked BEFORE any DB lookup, so a fake UUID is sufficient for event/user IDs.
If the role check passes, the endpoint returns 404 (not found) – not 403.
"""

import pytest

FAKE_UUID = "00000000-0000-0000-0000-000000000001"


@pytest.mark.integration
@pytest.mark.parametrize(
    "method,path,body,forbidden_roles",
    [
        # Events – admin only
        (
            "POST",
            "/api/events",
            {"title": "T", "event_type": "earthquake", "severity": "high"},
            ["manager", "employee"],
        ),
        ("PATCH", f"/api/events/{FAKE_UUID}", {"title": "T"}, ["manager", "employee"]),
        ("DELETE", f"/api/events/{FAKE_UUID}", None, ["manager", "employee"]),
        # Reports – stats/team-status forbidden for employee
        ("GET", f"/api/events/{FAKE_UUID}/stats", None, ["employee"]),
        ("GET", f"/api/events/{FAKE_UUID}/stats/by-department", None, ["employee"]),
        ("GET", f"/api/events/{FAKE_UUID}/team-status", None, ["employee"]),
        # all-status – admin only
        ("GET", f"/api/events/{FAKE_UUID}/all-status", None, ["manager", "employee"]),
        # Notifications – manager+ only
        ("POST", f"/api/events/{FAKE_UUID}/remind", None, ["employee"]),
        ("GET", f"/api/events/{FAKE_UUID}/reminders", None, ["employee"]),
        # Users – list: manager+; create/patch/delete: admin only
        ("GET", "/api/users", None, ["employee"]),
        (
            "POST",
            "/api/users",
            {"employee_id": "X", "name": "X", "email": "x@x.com", "password": "x", "role": "employee"},
            ["manager", "employee"],
        ),
        ("PATCH", f"/api/users/{FAKE_UUID}", {"name": "X"}, ["manager", "employee"]),
        ("DELETE", f"/api/users/{FAKE_UUID}", None, ["manager", "employee"]),
    ],
)
async def test_forbidden_role_gets_403(
    client,
    admin_user,
    manager_user,
    employee_user,
    admin_headers,
    manager_headers,
    employee_headers,
    method,
    path,
    body,
    forbidden_roles,
):
    headers_map = {
        "admin": admin_headers,
        "manager": manager_headers,
        "employee": employee_headers,
    }
    for role in forbidden_roles:
        kwargs = {"headers": headers_map[role]}
        if body:
            kwargs["json"] = body
        r = await getattr(client, method.lower())(path, **kwargs)
        assert r.status_code == 403, f"{role} on {method} {path} expected 403, got {r.status_code}: {r.text}"


@pytest.mark.integration
@pytest.mark.parametrize(
    "method,path,body,allowed_roles",
    [
        # Events – admin only
        ("PATCH", f"/api/events/{FAKE_UUID}", {"title": "T"}, ["admin"]),
        ("DELETE", f"/api/events/{FAKE_UUID}", None, ["admin"]),
        # Reports – manager+
        ("GET", f"/api/events/{FAKE_UUID}/stats", None, ["manager", "admin"]),
        ("GET", f"/api/events/{FAKE_UUID}/team-status", None, ["manager", "admin"]),
        # all-status – admin only
        ("GET", f"/api/events/{FAKE_UUID}/all-status", None, ["admin"]),
        # Notifications
        ("POST", f"/api/events/{FAKE_UUID}/remind", None, ["manager", "admin"]),
        ("GET", f"/api/events/{FAKE_UUID}/reminders", None, ["manager", "admin"]),
        # Users
        ("GET", "/api/users", None, ["manager", "admin"]),
        ("PATCH", f"/api/users/{FAKE_UUID}", {"name": "X"}, ["admin"]),
        ("DELETE", f"/api/users/{FAKE_UUID}", None, ["admin"]),
    ],
)
async def test_allowed_role_does_not_get_403(
    client,
    admin_user,
    manager_user,
    employee_user,
    admin_headers,
    manager_headers,
    employee_headers,
    method,
    path,
    body,
    allowed_roles,
):
    headers_map = {
        "admin": admin_headers,
        "manager": manager_headers,
        "employee": employee_headers,
    }
    for role in allowed_roles:
        kwargs = {"headers": headers_map[role]}
        if body:
            kwargs["json"] = body
        r = await getattr(client, method.lower())(path, **kwargs)
        assert r.status_code != 403, f"{role} on {method} {path} should NOT be 403, got {r.status_code}: {r.text}"
        # Also verify not 401 (unauthenticated)
        assert r.status_code != 401, f"{role} on {method} {path} should NOT be 401, got {r.status_code}"
