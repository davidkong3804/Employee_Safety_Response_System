# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run the full stack (dev)
```bash
docker compose up --build -d    # start all services
docker compose down             # stop
docker compose down -v          # stop + wipe DB
docker compose logs -f backend  # tail logs
```

### Frontend dev server (local, no Docker)
```bash
cd frontend
pnpm dev          # Vite at http://localhost:5173; proxies /api/* to localhost:8000
```

### Backend tests (requires a running PostgreSQL)
```bash
# Integration tests need a test DB — spin one up first:
docker compose -f docker-compose.test.yml up -d db-test

# Run all backend tests from inside backend/
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://app:devpassword@localhost:5433/safety_response_test \
  pytest tests/integration/ -v --tb=short               # integration only
TEST_DATABASE_URL=postgresql+asyncpg://app:devpassword@localhost:5433/safety_response_test \
  pytest -v --cov=app --cov-report=html                 # all tests + HTML coverage in htmlcov/

# Unit tests only (no DB needed):
pytest tests/unit/ -v --tb=short

# Single test file:
pytest tests/integration/test_events.py -v -k "test_create_event"
```

### Frontend tests
```bash
cd frontend
pnpm test          # watch mode
pnpm test --run    # run once (CI)
pnpm test --run --coverage
npx tsc --noEmit   # type-check without building
```

### E2E tests (requires full stack running)
```bash
docker compose up -d            # start the stack
cd tests/e2e
npx playwright test             # all specs
npx playwright test specs/auth.spec.ts   # single spec
npx playwright test --ui        # interactive UI mode
npx playwright show-report      # view last HTML report
```

### Performance tests (requires seed data in dev stack)
```bash
cd tests/performance
locust -f locustfile.py --headless --host http://localhost:8000 \
  --users 38 --spawn-rate 5 --run-time 60s \
  --html reports/normal_$(date +%Y%m%d).html
```

---

## Architecture

### Infrastructure notes

**Alembic is installed but not used.** Schema is created entirely by SQLAlchemy `Base.metadata.create_all` on startup (`main.py` lifespan). There are no migration files — do not run `alembic upgrade` or generate revisions.

**Redis is configured but not implemented.** `config.py` reads `REDIS_URL` and the Docker Compose file includes a Redis service, but no business logic currently uses it. Reserved for future use.

**API docs:** Swagger UI at `http://localhost:8000/docs` when the backend is running.

**Architecture docs:** `docs/` contains `architecture.md`, `er-diagram.md`, `sequence-diagrams.md`, `api-spec.md`, `user-stories.md`, `testing.md`.

### Backend — FastAPI modular monolith

`backend/app/` layout:
- `main.py` — FastAPI app + lifespan (creates tables, runs `seed_data()` on every startup)
- `config.py` — Pydantic-Settings; reads env vars: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`
- `database.py` — Single global `async_engine` + `get_db` dependency (yields `AsyncSession`)
- `dependencies.py` — `get_current_user` (JWT decode → DB lookup), `require_role(*roles)` factory
- `modules/<name>/` — Each module is self-contained: `router.py`, `models.py`, `schemas.py`

Modules: `auth`, `events`, `reports`, `users`, `notifications`

**Key business logic:**
- `POST /api/events` (admin only): after inserting an `Event`, immediately inserts `SafetyReport` placeholder rows for **every active user**. This is how "unreported" status is tracked — a placeholder row with `status=null`.
- `PATCH /api/events/{id}` with `status=closed`: sets `closed_at` to UTC now.
- `DELETE /api/events/{id}`: cascades to `safety_reports` and `reminders`.
- `POST /api/events/{id}/remind`: inserts a `Reminder` row per unreported user (increments `reminder_count` on repeat).
- `GET /api/events/{id}/team-status` filters to the requesting manager's direct reports via `User.manager_id` (self-referential FK). Managers see only their own team.

**Auth:** JWT stored in `localStorage`. Token payload: `sub` = `user.id` (UUID string). Roles: `admin`, `manager`, `employee`.

### Frontend — React SPA

`frontend/src/` layout:
- `main.tsx` — Mounts app + `<Toaster>` (react-hot-toast)
- `App.tsx` — Routes; `<ProtectedRoute>` wraps role-specific pages
- `contexts/AuthContext.tsx` — JWT state; `login()` stores token to localStorage, `logout()` clears it
- `api/client.ts` — Axios instance; request interceptor injects `Authorization: Bearer <token>`; response interceptor clears token and redirects to `/login` on 401 **except** for the `/auth/login` endpoint itself (to allow error toasts to render)
- `pages/employee/` — Home, ReportPage, PeerStatus
- `pages/manager/` — Dashboard (Recharts pie+bar, auto-refresh 30s)
- `pages/admin/` — EventManagement, UserManagement, Analytics
- `i18n/en.json` + `i18n/zh-TW.json` — All UI strings; default locale is `zh-TW`

**Vite dev proxy:** `/api/*` → `http://localhost:8000` (configured in `vite.config.ts`). The Docker frontend container uses `VITE_API_URL` env var instead.

### Test infrastructure

**Backend conftest** (`backend/tests/conftest.py`):
- `setup_database` (session-scoped): drops + recreates all tables once per pytest session. Uses a **separate engine** that is disposed immediately so it doesn't bleed into function-scoped event loops.
- `db_session` (function-scoped): creates a fresh engine per test, opens a connection-level transaction, yields an `AsyncSession`, then **rolls back** — each test is fully isolated without truncation.
- `client`: overrides `get_db` dependency to use the test session; disables `seed_data()` via a no-op lifespan.
- `active_event` fixture: creates an event + 3 placeholder `SafetyReport` rows (one per test user) to mirror production behavior.
- Test DB URL: `TEST_DATABASE_URL` env var (default: `localhost:5432/safety_response_test`); the `docker-compose.test.yml` exposes it on port **5433**.

**E2E fixtures** (`tests/e2e/fixtures/auth.fixture.ts`):
- `adminPage`, `managerPage`, `employeePage` — each is an isolated Playwright `BrowserContext` logged in as the corresponding seed account (A001, M001, E001; password: `password123`).
- Button/link selectors must be locale-safe — use regex (`/login|登入/i`) or `href`-based selectors, because the UI defaults to zh-TW.

### CI pipeline (`.github/workflows/ci.yml`)

Four jobs (1–3 run in parallel; 4 is gated on 2 and 3):
1. **backend-unit** — no DB, runs `tests/unit/`
2. **backend-integration** — PostgreSQL service, runs `tests/integration/`; uploads `coverage.xml`
3. **frontend-unit** — pnpm + vitest; uploads frontend coverage
4. **e2e** — `needs: [backend-integration, frontend-unit]`; spins up `docker compose`, waits for `/health`, runs Playwright

Performance (Locust) tests are **not** run in CI — execute manually with the dev stack.

### Demo seed data

38 users seeded on every backend startup: `A001`–`A003` (admin), `M001`–`M005` (manager), `E001`–`E030` (employee). All use password `password123`. Two events with mixed report statuses are pre-seeded. Seed is idempotent (skips if users already exist).
