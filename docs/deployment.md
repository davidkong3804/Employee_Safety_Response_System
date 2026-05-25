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

`k8s/02-secret.yaml` is **gitignored** — secrets never enter version
control. Create it from the committed template before applying:

```bash
cp k8s/02-secret.yaml.example k8s/02-secret.yaml
openssl rand -hex 32          # generate a strong JWT_SECRET
# then edit k8s/02-secret.yaml — set JWT_SECRET, POSTGRES_PASSWORD,
# and the password embedded in DATABASE_URL (must match POSTGRES_PASSWORD)
```

The `.example` file has a non-`.yaml` extension on purpose, so
`kubectl apply -f k8s/` skips the template and applies only the real
secret. For production, prefer GCP Secret Manager (Secrets Store CSI
driver) over a plain Secret, and prefer Cloud SQL over the in-cluster
`03-postgres.yaml`.

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

- Backend HPA: 3–60 pods at 60% CPU (`k8s/07-backend-hpa.yaml`).
- Frontend HPA: 1–10 pods (`k8s/09-frontend-hpa.yaml`).
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

PgBouncer (`k8s/12-pgbouncer.yaml`) sits between backend pods and PostgreSQL
in transaction pooling mode, multiplexing many client connections into ~50
real server connections:

```
60 backend pods  x  (DB_POOL_SIZE=10 + DB_MAX_OVERFLOW=5)  =  900 client conns
                                                              ↓ PgBouncer
                                                           ≤ 50 real DB conns
```

Pool sizes are in `k8s/01-configmap.yaml`. Without PgBouncer the formula is:

```
maxReplicas x (DB_POOL_SIZE + DB_MAX_OVERFLOW)  <  max_connections
```

## Stage 3: Production infrastructure (GKE)

### 3-A: PgBouncer (connection pooler)

Deploy PgBouncer before raising `maxReplicas` beyond ~110 pods (350 / 3):

```bash
kubectl apply -f k8s/12-pgbouncer.yaml
kubectl -n safety-system rollout status deployment/pgbouncer
```

Then update `k8s/02-secret.yaml` to use the PgBouncer URL and re-apply:

```bash
# In k8s/02-secret.yaml, uncomment Option B:
# DATABASE_URL: "postgresql+asyncpg://app:<pw>@pgbouncer:5432/safety_response"
kubectl apply -f k8s/02-secret.yaml
kubectl -n safety-system rollout restart deployment/backend
```

Verify: `kubectl -n safety-system exec deploy/pgbouncer -- pgbouncer -v`

### 3-C: Cloud Memorystore for Redis (HA)

```bash
# Provision Standard Tier instance (has replica + automatic failover)
gcloud redis instances create safety-redis \
  --region=REGION \
  --tier=standard \
  --size=1 \
  --redis-version=redis_7_0

# Get private IP
gcloud redis instances describe safety-redis --region=REGION --format='get(host)'
```

Update `k8s/01-configmap.yaml`:

```yaml
REDIS_URL: "redis://MEMORYSTORE_PRIVATE_IP:6379"
```

Then re-apply the ConfigMap and restart backends. Once Memorystore is live,
`k8s/04-redis.yaml` can be removed.

### 3-B: Cloud SQL HA (high-availability database)

```bash
# 1. Create a PostgreSQL 16 instance with HA (regional persistent disk + standby)
gcloud sql instances create safety-postgres \
  --database-version=POSTGRES_16 \
  --tier=db-g1-small \
  --region=REGION \
  --availability-type=regional \
  --storage-auto-increase

# 2. Set the app user password (must match POSTGRES_PASSWORD in the secret)
gcloud sql users set-password app \
  --instance=safety-postgres \
  --password=REPLACE_WITH_A_STRONG_DB_PASSWORD

# 3. Create the database
gcloud sql databases create safety_response --instance=safety-postgres

# 4. Create a GCP service account for Cloud SQL Auth Proxy
gcloud iam service-accounts create safety-backend \
  --display-name="Safety System Backend"
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:safety-backend@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

# 5. Bind GCP SA to the Kubernetes SA (Workload Identity)
gcloud iam service-accounts add-iam-policy-binding \
  safety-backend@PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:PROJECT_ID.svc.id.goog[safety-system/backend-sa]"
```

Get the instance connection name:

```bash
gcloud sql instances describe safety-postgres --format='get(connectionName)'
# → PROJECT_ID:REGION:safety-postgres
```

Update `k8s/02-secret.yaml` — uncomment Option C and add the connection name:

```yaml
DATABASE_URL: "postgresql+asyncpg://app:<pw>@127.0.0.1:5432/safety_response"
CLOUDSQL_INSTANCE_CONNECTION_NAME: "PROJECT_ID:REGION:safety-postgres"
```

Apply the Auth Proxy sidecar patch and restart:

```bash
kubectl apply -f k8s/13-cloudsql-proxy.yaml
kubectl apply -f k8s/02-secret.yaml
kubectl -n safety-system rollout restart deployment/backend
```

Run the db-init Job once against Cloud SQL to create the schema:

```bash
kubectl -n safety-system delete job db-init --ignore-not-found
kubectl apply -f k8s/05-db-init-job.yaml
kubectl -n safety-system wait --for=condition=complete job/db-init --timeout=180s
```

Once all pods are connected to Cloud SQL, `k8s/03-postgres.yaml` can be removed.

## Known limitations / next steps

- **No schema migrations.** Schema changes currently require recreating
  tables via the init job. Adopt Alembic when the schema needs to evolve
  against live data.
