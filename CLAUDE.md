# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Cloud-native emergency safety reporting system. During a critical incident (earthquake, fire, etc.) employees one-tap report their safety status; managers monitor a real-time dashboard; admins manage events and users. Three roles (`employee`, `manager`, `admin`) with JWT auth.

## Commands

### Full stack (Docker Compose)
```bash
docker compose up --build -d      # db, redis, backend-init (once), backend (:8000), frontend (:5173)
docker compose ps
docker compose down               # add -v to also drop the database volume
docker compose logs -f backend    # tail backend logs
```
The `backend-init` service runs `python -m app.init_db --seed` once (creates tables + seeds 38 demo users), then exits; `backend` waits for it to complete. Tables/seeding do NOT happen on app startup. Demo accounts: `A001`/`M001`/`E001`, password `password123`. The compose `frontend` is the production nginx build (no hot-reload) — for frontend dev run `pnpm dev` on the host instead.

### Database init
```bash
python -m app.init_db             # Create tables only (run from backend/)
python -m app.init_db --seed      # Create tables + load demo data
```
Idempotent and safe to re-run. Runs as the Compose `backend-init` service and the k8s `db-init` Job.

### Kubernetes (GKE)
```bash
cp k8s/02-secret.yaml.example k8s/02-secret.yaml               # fill real values; gitignored
kubectl apply -f k8s/                                          # numbered, applies in order
kubectl -n safety-system wait --for=condition=complete job/db-init --timeout=180s
```
Manifests live in `k8s/` (namespace `safety-system`). `k8s/02-secret.yaml` is gitignored — create it from the `.example` template before the first apply. See `docs/deployment.md` for image build/push and the full procedure.

### Backend (FastAPI, Python 3.12) — run from `backend/`
```bash
pip install -r requirements.txt
pytest tests/unit/ -v --tb=short                 # Unit tests, no DB
pytest tests/integration/ -v --tb=short          # Integration tests, needs PostgreSQL
pytest tests/integration/test_events.py -v       # Single file
pytest tests/integration/test_events.py::test_name -v   # Single test
pytest -v --cov=app --cov-report=html            # All tests + HTML coverage in htmlcov/
```
Integration tests need a Postgres reachable via `TEST_DATABASE_URL` (defaults to `postgresql+asyncpg://app:devpassword@localhost:5432/safety_response_test`). `docker-compose.test.yml` runs the full suite in a container against a tmpfs Postgres on host port 5433.

### Frontend (React 18 + Vite + TS) — run from `frontend/`
```bash
pnpm install
pnpm dev                          # Dev server on :5173, proxies /api -> :8000
pnpm build                        # tsc -b && vite build
pnpm vitest run --coverage        # Unit tests (Vitest + Testing Library + MSW)
pnpm vitest run src/__tests__/components/StatusBadge.test.tsx   # Single file
npx tsc --noEmit                  # Type-check without building
```

### E2E (Playwright) — run from `tests/e2e/`
```bash
npm install && npx playwright install --with-deps chromium
npx playwright test               # Needs full stack running; BASE_URL defaults to http://localhost:5173
npx playwright test specs/auth.spec.ts   # Single spec
npx playwright test --ui          # Interactive UI mode
npx playwright show-report        # View last HTML report
```

### Performance tests (Locust) — run from `tests/performance/`
```bash
locust -f locustfile.py --headless --host http://localhost:8000 \
  --users 38 --spawn-rate 5 --run-time 60s \
  --html reports/normal_$(date +%Y%m%d).html
```
Not run in CI — execute manually against the dev stack with seed data.

CI (`.github/workflows/ci.yml`) runs four jobs: backend-unit, backend-integration, frontend-unit, then e2e (which boots the full Docker stack).

## Architecture

### Backend — modular monolith
`backend/app/modules/<name>/` each holds `router.py`, `schemas.py`, `models.py` and is self-contained, designed for future microservice extraction. Modules: `auth`, `events`, `reports`, `users`, `notifications`. All routers are mounted in `app/main.py` under `/api/*`.

- **Async throughout** — SQLAlchemy 2.0 async + asyncpg. `app/database.py` exposes the global `engine`, `Base`, and `get_db()` (a request-scoped session that commits on success / rolls back on exception).
- **Auth** — `app/dependencies.py`: `get_current_user` decodes the JWT; `require_role(*roles)` is a dependency factory for RBAC. Token creation/`hash_password` live in `auth/router.py`. JWT is stored in `localStorage`; token payload `sub` = `user.id` (UUID string).
- **Config** — `app/config.py` reads env vars (`DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `REDIS_URL`, `DB_POOL_*`) into a pydantic `Settings` singleton.
- **DB schema** — 4 tables: `users`, `events`, `safety_reports`, `reminders`. Creating an event spawns one placeholder `SafetyReport` row per relevant user (filtered by event `facilities` if set); reporting fills it in. `User` has a self-referential `manager_id` FK so `team-status` queries filter to direct reports.
- **Initialization** — `app/init_db.py` is the standalone create-tables(+seed) script. App startup (`main.py` lifespan) does NOT touch the schema — running it per pod races across replicas. There are no migrations; schema changes mean recreating tables via the init job. **Alembic is installed but not used.**
- **Health** — `/health` is liveness (cheap, no deps); `/health/ready` is readiness (runs `SELECT 1`, returns 503 if the DB is down).
- **Connection pool** — `app/database.py` engine is tuned via `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` etc. so `replicas x pool` stays under Postgres `max_connections`.
- **Redis** — `REDIS_URL` is read from config and a Redis service is in compose/k8s, but no business logic currently uses it. Reserved for future use.

**Key business logic:**
- `POST /api/events` (admin): inserts an `Event` then creates one placeholder `SafetyReport` row per relevant user (all active users, or scoped by `facilities`). This is how "unreported" status is tracked — a placeholder row with `status=null`.
- `PATCH /api/events/{id}` with `status=closed`: sets `closed_at` to UTC now.
- `DELETE /api/events/{id}`: cascades to `safety_reports` and `reminders`.
- `POST /api/events/{id}/remind`: inserts a `Reminder` row per unreported user (increments `reminder_count` on repeat).
- `GET /api/events/{id}/team-status` filters by the requesting manager's direct reports via `User.manager_id`.

### Backend tests
`backend/tests/conftest.py` has two non-obvious mechanisms:
1. It sets `DATABASE_URL` to the test DB **before importing the app**, and replaces the app lifespan with a no-op so tests fully control schema setup/teardown.
2. Each test gets its own `create_async_engine` + connection wrapped in a transaction that rolls back on teardown — this keeps asyncpg in the same function-scoped event loop and avoids cross-loop Future errors. Don't refactor fixtures to share a session-scoped engine.

`client` fixture overrides `get_db` with the per-test session. Role/header fixtures: `admin_user`/`manager_user`/`employee_user` and `*_headers`, plus `active_event` (creates an event + placeholder `SafetyReport` rows mirroring production behavior). Test DB URL: `TEST_DATABASE_URL` env var (default `localhost:5432`); `docker-compose.test.yml` exposes a tmpfs Postgres on port 5433.

### Frontend
React Router SPA. `App.tsx` defines routes; `ProtectedRoute` gates on auth and an optional `roles` prop. `AuthContext` holds JWT state — `login()` writes the token to localStorage, `logout()` clears it. `api/client.ts` is the shared axios instance — its request interceptor injects `Authorization: Bearer <token>`; its response interceptor clears the token and redirects to `/login` on 401 **except** for `/auth/login` itself (so the login page can render its own error toast). Pages are grouped by role: `pages/employee/` (Home, ReportPage, PeerStatus), `pages/manager/` (Dashboard with Recharts pie/bar + 30s auto-refresh), `pages/admin/` (EventManagement, UserManagement, Analytics). i18n via react-i18next (`src/i18n/en.json`, `zh-TW.json`); default locale is `zh-TW`.

Vite dev proxy: `/api/*` → `http://localhost:8000` (in `vite.config.ts`). The Docker frontend uses the `VITE_API_URL` env var instead.

### E2E test infrastructure
`tests/e2e/fixtures/auth.fixture.ts`: `adminPage`, `managerPage`, `employeePage` — each is an isolated Playwright `BrowserContext` already logged in as A001 / M001 / E001 (password `password123`). Button/link selectors must be **locale-safe** — use regex (`/login|登入/i`) or `href`-based selectors because the UI defaults to zh-TW.

### Demo seed data
38 users across 5 departments and 2 facilities (Fab14, Fab18): `A001`–`A003` (admin), `M001`–`M005` (manager), `E001`–`E030` (employee). All use password `password123`. Two events with mixed report statuses are pre-seeded. Seed is idempotent (skips if users already exist).

## Documentation

`docs/` holds the design specs that drive this codebase — consult before changing behavior:
`architecture.md`, `deployment.md` (Docker Compose + GKE deployment), `er-diagram.md`, `sequence-diagrams.md`, `api-spec.md`, `user-stories.md` (9 user stories + acceptance criteria), `testing.md`.
