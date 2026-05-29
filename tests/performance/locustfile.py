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

import os
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests
from locust import HttpUser, between, events, task
from locust.runners import MasterRunner, WorkerRunner

# Pre-warm pool size sentinels — see warmup_tokens() for the rationale.
WARMUP_MAX_TOKENS = 15000        # absolute upper bound (~ Locust GitHub Action runner mem budget)
WARMUP_PARALLELISM = 100         # concurrent login requests during warmup
WARMUP_OVERFETCH_FACTOR = 2     # warm 2× VU count so random.choice has slack

# ---------------------------------------------------------------------------
# Seed credentials (password123 for all)
#
# Capacity must match backend/app/seed.py LOAD_TEST_MAX_EMPLOYEES — currently
# 500. The first 30 are hand-crafted demo accounts (3-digit IDs); the rest
# are auto-generated test accounts with 4-digit IDs.
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

# Shared cache – populated once when an AdminUser starts up
_active_event_ids: list[str] = []

# Token pool – populated once at test_start by warmup_tokens(), keyed by
# employee_id. Lets every user reuse a pre-fetched JWT instead of paying the
# bcrypt login cost on every on_start, so the load test measures the real
# throughput of the business endpoints rather than the bcrypt bottleneck.
_token_pool: dict[str, str] = {}


@events.test_start.add_listener
def warmup_tokens(environment, **kwargs) -> None:
    import traceback
    with open("/tmp/warmup.log", "a") as debug_f:
        debug_f.write(f"--- warmup_tokens triggered --- \n")
        debug_f.write(f"environment.host: {environment.host}\n")
        debug_f.write(f"environment.runner: {type(environment.runner).__name__ if environment.runner else 'None'}\n")

    try:
        host = (environment.host or "").rstrip("/")
        if not host:
            with open("/tmp/warmup.log", "a") as debug_f:
                debug_f.write("skipping due to empty host\n")
            print("[warmup] no host configured – skipping token pre-fetch")
            return

        # Derive how many tokens to warm from the planned VU count
        num_users = 0
        try:
            num_users = int(getattr(environment.parsed_options, "num_users", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            num_users = 0
        
        with open("/tmp/warmup.log", "a") as debug_f:
            debug_f.write(f"Derived num_users: {num_users}\n")

        target_employee_count = (
            min(num_users * WARMUP_OVERFETCH_FACTOR, len(EMPLOYEE_CREDS), WARMUP_MAX_TOKENS)
            if num_users > 0
            else min(len(EMPLOYEE_CREDS), WARMUP_MAX_TOKENS)
        )
        employees_to_warm = EMPLOYEE_CREDS[:target_employee_count]
        all_creds = employees_to_warm + MANAGER_CREDS + [ADMIN_CREDS]

        with open("/tmp/warmup.log", "a") as debug_f:
            debug_f.write(f"Target count to warm: {len(all_creds)}\n")

        def _login_one(creds: dict) -> Optional[tuple]:
            try:
                r = requests.post(f"{host}/api/auth/login", json=creds, timeout=30)
                if r.status_code == 200:
                    return creds["employee_id"], r.json()["access_token"]
            except Exception as e:
                # Log specific requests errors
                with open("/tmp/warmup.log", "a") as debug_f:
                    debug_f.write(f"Login request failed for {creds.get('employee_id')}: {str(e)}\n")
                return None
            return None

        ok = 0
        with open("/tmp/warmup.log", "a") as debug_f:
            debug_f.write("Starting ThreadPoolExecutor warmup...\n")
            
        with ThreadPoolExecutor(max_workers=WARMUP_PARALLELISM) as ex:
            for result in ex.map(_login_one, all_creds):
                if result:
                    _token_pool[result[0]] = result[1]
                    ok += 1

        with open("/tmp/warmup.log", "a") as debug_f:
            debug_f.write(f"ThreadPoolExecutor finished. Successfully pre-fetched: {ok}/{len(all_creds)} tokens\n")

        print(
            f"[warmup] pre-fetched {ok}/{len(all_creds)} tokens from {host} "
            f"(num_users={num_users}, parallelism={WARMUP_PARALLELISM})"
        )

        if isinstance(environment.runner, MasterRunner):
            with open("/tmp/warmup.log", "a") as debug_f:
                debug_f.write(f"Runner is MasterRunner. Broadcasting {len(_token_pool)} tokens to workers...\n")
            print(f"[warmup] broadcasting {len(_token_pool)} pre-warmed tokens to all workers")
            environment.runner.send_message("warmup_tokens", _token_pool)
            with open("/tmp/warmup.log", "a") as debug_f:
                debug_f.write("Broadcasting message sent successfully via ZMQ.\n")

    except Exception as e:
        with open("/tmp/warmup.log", "a") as debug_f:
            debug_f.write(f"CRITICAL ERROR in warmup_tokens: {str(e)}\n")
            debug_f.write(traceback.format_exc() + "\n")


def on_warmup_tokens(environment, msg, **kwargs):
    global _token_pool
    try:
        _token_pool.update(msg.data)
        with open("/tmp/warmup_worker.log", "a") as debug_f:
            debug_f.write(f"Received {len(msg.data)} pre-warmed tokens from master. Current pool size: {len(_token_pool)}\n")
        print(f"[worker] received {len(msg.data)} pre-warmed tokens from master")
    except Exception as e:
        with open("/tmp/warmup_worker.log", "a") as debug_f:
            debug_f.write(f"ERROR in on_warmup_tokens: {str(e)}\n")


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    if not isinstance(environment.runner, MasterRunner):
        environment.runner.register_message("warmup_tokens", on_warmup_tokens)


class _BaseUser(HttpUser):
    abstract = True
    # Aggressive wait_time so 500 simulated VUs generate request volume
    # equivalent to ~2000 conventional VUs (1-3s wait). Each VU now issues
    # roughly 1 request per 0.4s instead of every 2s, multiplying offered
    # load 5× without quintupling the Locust client's own greenlet count
    # (which would overwhelm the GitHub Actions runner at 2 vCPU).
    #
    # Set LOAD_TEST_WAIT_FAST=0 in the env to revert to the realistic
    # think-time profile.
    wait_time = (
        between(1, 3)
        if os.environ.get("LOAD_TEST_WAIT_FAST", "1") == "0"
        else between(0.2, 0.6)
    )
    _token: Optional[str] = None

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def _login(self, creds: dict) -> None:
        # If distributed stress test is active, wait briefly for master's token pool broadcast.
        # This resolves the race condition where Workers spawn VUs before Master completes its token warmup.
        import time
        retries = 30
        while not _token_pool and retries > 0:
            # We only wait if we are running in worker mode (ZMQ communication is active)
            # and master is pre-warming.
            time.sleep(1)
            retries -= 1

        # Prefer the token pre-fetched at test_start (see warmup_tokens) so the
        # bcrypt login cost does not pollute the metrics of other endpoints.
        cached = _token_pool.get(creds["employee_id"])
        if cached:
            self._token = cached
            return
        # Fallback: live login (e.g. interactive web UI, or warmup skipped).
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
