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

import random

from locust import HttpUser, between, task

# ---------------------------------------------------------------------------
# Seed credentials (password123 for all)
# ---------------------------------------------------------------------------
ADMIN_CREDS = {"employee_id": "A001", "password": "password123"}
MANAGER_CREDS = [
    {"employee_id": f"M{i:03d}", "password": "password123"} for i in range(1, 6)
]
EMPLOYEE_CREDS = [
    {"employee_id": f"E{i:03d}", "password": "password123"} for i in range(1, 31)
]

# Shared cache – populated once when an AdminUser starts up
_active_event_ids: list[str] = []


class _BaseUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)
    _token: str | None = None

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


# ---------------------------------------------------------------------------
# Employee (weight 30)
# ---------------------------------------------------------------------------
class EmployeeUser(_BaseUser):
    weight = 30

    def on_start(self) -> None:
        self._login(random.choice(EMPLOYEE_CREDS))

    @task(5)
    def list_events(self) -> None:
        self.client.get("/api/events", headers=self._headers(), name="GET /api/events")

    @task(3)
    def submit_report(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        self.client.post(
            f"/api/events/{event_id}/report",
            json={"status": random.choice(["safe", "need_help"])},
            headers=self._headers(),
            name="POST /api/events/{id}/report",
        )

    @task(2)
    def get_my_report(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        self.client.get(
            f"/api/events/{event_id}/my-report",
            headers=self._headers(),
            name="GET /api/events/{id}/my-report",
        )

    @task(1)
    def health_check(self) -> None:
        self.client.get("/health", name="GET /health")


# ---------------------------------------------------------------------------
# Manager (weight 5)
# ---------------------------------------------------------------------------
class ManagerUser(_BaseUser):
    weight = 5

    def on_start(self) -> None:
        self._login(random.choice(MANAGER_CREDS))

    @task(3)
    def get_team_status(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        self.client.get(
            f"/api/events/{event_id}/team-status",
            headers=self._headers(),
            name="GET /api/events/{id}/team-status",
        )

    @task(2)
    def get_stats(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        self.client.get(
            f"/api/events/{event_id}/stats",
            headers=self._headers(),
            name="GET /api/events/{id}/stats",
        )

    @task(1)
    def trigger_reminders(self) -> None:
        if not _active_event_ids:
            return
        event_id = random.choice(_active_event_ids)
        self.client.post(
            f"/api/events/{event_id}/remind",
            headers=self._headers(),
            name="POST /api/events/{id}/remind",
        )


# ---------------------------------------------------------------------------
# Admin (weight 3) – also populates shared event cache
# ---------------------------------------------------------------------------
class AdminUser(_BaseUser):
    weight = 3

    def on_start(self) -> None:
        self._login(ADMIN_CREDS)
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
