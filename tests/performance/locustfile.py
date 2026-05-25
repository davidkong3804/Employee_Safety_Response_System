"""
Locust performance test for the Employee Safety Response System.

Usage:
  # Normal load (38 concurrent users, 60s)
  locust -f locustfile.py --headless --host http://localhost:8000 \
    --users 38 --spawn-rate 5 --run-time 60s \
    --html reports/normal_$(date +%Y%m%d_%H%M%S).html

  # Stress test (100 concurrent users, 120s)
  locust -f locustfile.py --headless --host http://localhost:8000 \
    --users 100 --spawn-rate 20 --run-time 120s \
    --html reports/stress_$(date +%Y%m%d_%H%M%S).html

  # Interactive web UI
  locust -f locustfile.py --host http://localhost:8000

Acceptance thresholds (check in the HTML report):
  - p95 response time < 500ms for POST /report
  - p95 response time < 200ms for GET /health
  - Error rate < 1% under normal load (38 users)
  - Throughput > 100 RPS for read endpoints
"""

import itertools
import random
from typing import Optional

from locust import HttpUser, between, task

# ---------------------------------------------------------------------------
# Seed credentials (password123 for all)
#
# Capacity must match backend/app/seed.py LOAD_TEST_MAX_EMPLOYEES — currently
# 15000. The first 30 are hand-crafted demo accounts (3-digit IDs); the rest
# are auto-generated test accounts with 4-or-more-digit IDs.
# ---------------------------------------------------------------------------
LOAD_TEST_MAX_EMPLOYEES = 15000

ADMIN_CREDS = {"employee_id": "A001", "password": "password123"}
MANAGER_CREDS = [
    {"employee_id": f"M{i:03d}", "password": "password123"} for i in range(1, 6)
]
EMPLOYEE_CREDS = (
    [{"employee_id": f"E{i:03d}", "password": "password123"} for i in range(1, 31)]
    + [{"employee_id": f"E{i:04d}", "password": "password123"}
       for i in range(31, LOAD_TEST_MAX_EMPLOYEES + 1)]
)

# Round-robin iterators so each virtual user gets a unique slot (cycles if
# more virtual users than real accounts, but avoids hot-spot collisions).
_employee_cycle = itertools.cycle(EMPLOYEE_CREDS)
_manager_cycle  = itertools.cycle(MANAGER_CREDS)
_admin_cycle    = itertools.cycle([ADMIN_CREDS])

# Shared cache – populated once when an AdminUser starts up
_active_event_ids = []


class _BaseUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)
    _token: Optional[str] = None

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def _login(self, creds: dict) -> None:
        with self.client.post(
            "/api/auth/login",
            json=creds,
            catch_response=True,
            name="/api/auth/login",
        ) as r:
            if r.status_code == 200:
                self._token = r.json()["access_token"]
            else:
                r.failure(f"Login failed {r.status_code}")

    def _refresh_token(self, creds: dict) -> None:
        """Re-login if token seems stale (called on 401)."""
        self._login(creds)


# ---------------------------------------------------------------------------
# Employee (weight 30)
# ---------------------------------------------------------------------------
class EmployeeUser(_BaseUser):
    weight = 30

    def on_start(self) -> None:
        self._creds = next(_employee_cycle)
        self._login(self._creds)

    @task(5)
    def list_events(self) -> None:
        self.client.get("/api/events", headers=self._headers(), name="GET /api/events")

    @task(3)
    def submit_report(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        with self.client.post(
            f"/api/events/{event_id}/report",
            json={"status": random.choice(["safe", "need_help"])},
            headers=self._headers(),
            name="POST /api/events/{id}/report",
            catch_response=True,
        ) as r:
            if r.status_code == 401:
                self._refresh_token(self._creds)

    @task(2)
    def get_my_report(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        with self.client.get(
            f"/api/events/{event_id}/my-report",
            headers=self._headers(),
            name="GET /api/events/{id}/my-report",
            catch_response=True,
        ) as r:
            if r.status_code == 401:
                self._refresh_token(self._creds)

    @task(1)
    def health_check(self) -> None:
        self.client.get("/health", name="GET /health")


# ---------------------------------------------------------------------------
# Manager (weight 5)
# ---------------------------------------------------------------------------
class ManagerUser(_BaseUser):
    weight = 5

    def on_start(self) -> None:
        self._creds = next(_manager_cycle)
        self._login(self._creds)

    @task(3)
    def get_team_status(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        with self.client.get(
            f"/api/events/{event_id}/team-status",
            headers=self._headers(),
            name="GET /api/events/{id}/team-status",
            catch_response=True,
        ) as r:
            if r.status_code == 401:
                self._refresh_token(self._creds)

    @task(2)
    def get_stats(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        with self.client.get(
            f"/api/events/{event_id}/stats",
            headers=self._headers(),
            name="GET /api/events/{id}/stats",
            catch_response=True,
        ) as r:
            if r.status_code == 401:
                self._refresh_token(self._creds)

    @task(1)
    def trigger_reminders(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        with self.client.post(
            f"/api/events/{event_id}/remind",
            headers=self._headers(),
            name="POST /api/events/{id}/remind",
            catch_response=True,
        ) as r:
            if r.status_code == 401:
                self._refresh_token(self._creds)


# ---------------------------------------------------------------------------
# Admin (weight 3) – also populates shared event cache
# ---------------------------------------------------------------------------
class AdminUser(_BaseUser):
    weight = 3

    def on_start(self) -> None:
        self._creds = next(_admin_cycle)
        self._login(self._creds)
        # Populate shared cache with active event IDs
        r = self.client.get("/api/events", headers=self._headers())
        if r.status_code == 200:
            global _active_event_ids
            _active_event_ids = [e["id"] for e in r.json() if e["status"] == "active"]

    @task(3)
    def get_all_status(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        self.client.get(
            f"/api/events/{event_id}/all-status",
            headers=self._headers(),
            name="GET /api/events/{id}/all-status",
        )

    @task(2)
    def get_stats_by_dept(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        self.client.get(
            f"/api/events/{event_id}/stats/by-department",
            headers=self._headers(),
            name="GET /api/events/{id}/stats/by-department",
        )

    @task(1)
    def list_users(self) -> None:
        self.client.get("/api/users", headers=self._headers(), name="GET /api/users")
