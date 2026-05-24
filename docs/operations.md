# Operations Guide

## Monitoring Stack

| Service | URL (local) | Purpose |
|---------|-------------|---------|
| Backend metrics | http://localhost:8000/metrics | Prometheus scrape endpoint |
| Prometheus | http://localhost:9090 | Metrics collection & alerting |
| Grafana | http://localhost:3001 | Dashboard visualization (admin/admin) |

### Key Metrics Collected

| Metric | Description |
|--------|-------------|
| `http_requests_total` | Total HTTP requests by handler, method, status |
| `http_request_duration_seconds` | Request latency histogram (p50/p90/p95/p99) |
| `http_request_size_bytes` | Request payload size |
| `http_response_size_bytes` | Response payload size |
| `up` | Whether Prometheus can scrape the target |

### Grafana Dashboard

Dashboard **"Safety Response System"** (`monitoring/grafana/provisioning/dashboards/safety-response.json`) provides:
- Request Per Second (RPS)
- Error Rate (4xx / 5xx)
- Response Time p95
- RPS by Endpoint
- Response Time p50 / p90 / p99

Auto-provisioned on `docker compose up` — available at http://localhost:3001.

---

## Alerting Rules

Defined in `monitoring/prometheus-rules.yml`:

| Alert | Condition | Severity |
|-------|-----------|----------|
| `BackendDown` | Backend unreachable for >1m | critical |
| `HighErrorRate` | 5xx rate >5% for >1m | critical |
| `HighLatency` | p95 >1s for >2m | warning |
| `High4xxRate` | 4xx rate >20% for >2m | warning |

---

## Health Checks

| Endpoint | Type | Description |
|----------|------|-------------|
| `GET /health` | Liveness | Process is up; dependency-free |
| `GET /health/ready` | Readiness | DB reachable (`SELECT 1`); returns 503 if not |

Kubernetes probes in `k8s/06-backend.yaml` use both endpoints:
- **livenessProbe** → `/health` (restarts pod if it fails)
- **readinessProbe** → `/health/ready` (removes pod from load balancer if DB is down)

---

## Scalability

### Horizontal Pod Autoscaler (HPA)

| Component | Min Replicas | Max Replicas | CPU Threshold |
|-----------|-------------|-------------|---------------|
| Backend | 1 | 30 | 70% |
| Frontend | 1 | 10 | 70% |

HPA scales up when CPU > 70% and scales down after 180s stabilization to avoid flapping.

### DB Connection Pool

Backend connects to PostgreSQL via a connection pool tuned via env vars:

| Env Var | Default | Description |
|---------|---------|-------------|
| `DB_POOL_SIZE` | 5 | Connections per pod |
| `DB_MAX_OVERFLOW` | 10 | Extra connections allowed |

Rule: `replicas × (pool_size + max_overflow) < postgres max_connections (350)`.

---

## Single Point of Failure Handling

### PostgreSQL
- **Risk**: Single StatefulSet instance — no streaming replication in current setup.
- **Local/Dev**: Data persisted in Docker volume `pgdata`; survives container restarts.
- **Production mitigation**: Use **Cloud SQL for PostgreSQL** (managed HA with automatic failover).
- **Recovery**: Re-run `python -m app.init_db --seed` after DB restore to recreate schema and seed data.

### Redis
- **Risk**: Single Redis instance — no Sentinel or Cluster mode.
- **Current usage**: Reserved for future caching; no business logic depends on it yet.
- **Production mitigation**: Use **Cloud Memorystore for Redis** (managed HA).
- **Impact if down**: Currently none; future cache misses would fall back to DB queries.

### Backend Pods
- **Handled by**: HPA + PodDisruptionBudget (`minAvailable: 1`) ensures at least one pod stays up during rolling updates.
- **Zero-downtime deploy**: Kubernetes rolling update strategy with readiness probe gates traffic.

### Frontend
- **Stateless**: Nginx serving static files — any pod can handle any request.
- **HPA**: Scales 1–10 replicas based on CPU.

---

## Runbook: Common Incidents

### Backend returns 500
1. Check logs: `docker compose logs backend --tail=50` or `kubectl logs -n safety-system deploy/backend`
2. Check DB connectivity: `GET /health/ready` — if 503, DB is down
3. Check connection pool exhaustion in Prometheus: `pg_stat_activity` or DB error in logs

### High latency alert fires
1. Check RPS spike in Grafana dashboard
2. Check DB query performance — look for slow queries in backend logs
3. If sustained: HPA should auto-scale; manually trigger if needed: `kubectl scale deploy/backend --replicas=3`

### Backend pod keeps restarting
1. Check liveness probe: `kubectl describe pod <pod-name>`
2. Check OOMKilled: `kubectl get pod <pod-name> -o json | jq '.status.containerStatuses[].lastState'`
3. Increase memory limits in `k8s/06-backend.yaml` if OOMKilled
