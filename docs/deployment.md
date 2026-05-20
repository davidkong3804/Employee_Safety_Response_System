# Deployment Guide

How to run the Employee Safety & Response System locally and on Kubernetes
(GKE). For the system design see [architecture.md](architecture.md).

## Deployment model

The backend is a **stateless** FastAPI app — auth is JWT, no server-side
sessions, no in-memory state. It scales horizontally: run N identical replicas
behind a load balancer. The frontend is a static SPA served by nginx.

One rule makes this work: **schema creation and demo seeding never run on app
startup**. With multiple replicas, doing that per pod races on DDL and
seeding. Instead a single run-once initializer (`python -m app.init_db`)
handles it — as a Docker Compose init service locally and a Kubernetes Job in
the cluster.

```
            Ingress / Load Balancer
                /            \
           /api               /*
             |                  |
        backend Svc        frontend Svc
        (3–30 pods, HPA)   (2–10 pods, HPA)
             |
        PostgreSQL  +  Redis
             ^
        db-init Job (runs once: create tables + seed)
```

## Local — Docker Compose

```bash
docker compose up --build -d      # db, redis, backend-init (once), backend, frontend
docker compose ps
docker compose down               # add -v to also drop the database volume
```

- `backend-init` runs `python -m app.init_db --seed`, then exits. `backend`
  waits for it via `depends_on: service_completed_successfully`.
- Frontend is the production nginx image; nginx reverse-proxies `/api` to the
  backend, so the browser makes same-origin calls (no CORS).
- URLs: frontend http://localhost:5173 · backend http://localhost:8000 ·
  Swagger http://localhost:8000/docs
- Demo accounts (password `password123`): `A001` admin · `M001` manager ·
  `E001` employee.

### Frontend hot-reload during development

The compose frontend is a static build, so it does not hot-reload. For active
frontend work run the dev server on the host instead:

```bash
cd frontend && pnpm install && pnpm dev   # :5173, proxies /api -> :8000
```

The backend container keeps `--reload` (a dev-only `command:` override in
`docker-compose.yml`); the image's default command has no `--reload`.

## Database initializer

`python -m app.init_db` — create tables only.
`python -m app.init_db --seed` — create tables and load demo data (or set
`SEED_DEMO_DATA=true`).

Both steps are idempotent: `create_all` skips existing tables; seeding is
skipped when any user already exists. Safe to re-run and to retry.

## Kubernetes (GKE)

All manifests live in `k8s/`, numbered so `kubectl apply` orders them
correctly. Namespace: `safety-system`.

### 1. Build and push images

GKE pulls from a registry — build both images and push to Artifact Registry,
then update the `image:` fields in `k8s/05-db-init-job.yaml`,
`k8s/06-backend.yaml`, and `k8s/08-frontend.yaml`.

```bash
REPO=asia-east1-docker.pkg.dev/PROJECT_ID/safety-response
docker build -t $REPO/safety-response-backend:v1 ./backend
docker build -t $REPO/safety-response-frontend:v1 ./frontend
docker push $REPO/safety-response-backend:v1
docker push $REPO/safety-response-frontend:v1
```

### 2. Set real secrets

Edit `k8s/02-secret.yaml` before applying. The committed values are dev
placeholders. Generate a real JWT secret with `openssl rand -hex 32`. For
production, prefer GCP Secret Manager (Secrets Store CSI driver) over a
plain Secret, and prefer Cloud SQL over the in-cluster `03-postgres.yaml`.

### 3. Apply

```bash
kubectl apply -f k8s/
kubectl -n safety-system wait --for=condition=complete job/db-init --timeout=180s
kubectl -n safety-system get pods,svc,hpa,ingress
```

`kubectl apply -f k8s/` brings up everything. The `db-init` Job retries
(`backoffLimit`) until Postgres is reachable, so apply order is not fragile.
The GKE Ingress takes a few minutes to provision the load balancer; get its
address with `kubectl -n safety-system get ingress safety-system`.

### Re-running the init Job

A Job spec is immutable. To re-run after a change:

```bash
kubectl -n safety-system delete job db-init
kubectl apply -f k8s/05-db-init-job.yaml
```

### Scaling

- Backend HPA: 3–30 pods at 70% CPU (`k8s/07-backend-hpa.yaml`).
- Frontend HPA: 2–10 pods (`k8s/09-frontend-hpa.yaml`).
- Manual: `kubectl -n safety-system scale deployment/backend --replicas=10`.
- HPA needs the metrics server — built in on GKE.

### Health probes

| Endpoint | Probe | Behaviour |
|----------|-------|-----------|
| `GET /health` | backend liveness | Cheap, no dependencies. A DB blip must not restart pods. |
| `GET /health/ready` | backend readiness | Runs `SELECT 1`; returns 503 if the DB is down so traffic is held off. |
| `GET /healthz` | frontend liveness/readiness | nginx returns `200 ok`. |

GKE derives each load-balancer health check from the pods' readiness probes.

## Connection-pool capacity

Each backend pod opens up to `DB_POOL_SIZE + DB_MAX_OVERFLOW` connections.
Keep the cluster total under Postgres `max_connections`:

```
maxReplicas x (DB_POOL_SIZE + DB_MAX_OVERFLOW)  <  max_connections
30          x (3            + 2              )  =  150  <  200
```

`max_connections=200` is set on the Postgres StatefulSet; pool sizes are in
`k8s/01-configmap.yaml`. If you raise `maxReplicas` substantially, put
**pgbouncer** (transaction pooling) between the backend and Postgres rather
than growing per-pod pools.

## Known limitations / next steps

- **Redis is provisioned but unused** by application code. Wire it up to cache
  the dashboard aggregation endpoints (`/api/events/{id}/stats*`) — at scale,
  the 30-second dashboard polling hammers those uncached queries.
- **In-cluster PostgreSQL** has no HA or automated backups. Use Cloud SQL for
  real production.
- **No schema migrations.** Schema changes currently require recreating
  tables via the init job. Adopt Alembic when the schema needs to evolve
  against live data.
