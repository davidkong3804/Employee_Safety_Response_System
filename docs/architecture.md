# System Architecture

## Overview

Employee Safety & Response System (企業營運緊急事件安全回報系統) adopts a **modular monolith** architecture for rapid development, with clear module boundaries designed for future migration to microservices on Kubernetes.

## Current Architecture (Local Prototype)

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                           │
│                                                             │
│  ┌──────────────┐     ┌──────────────────────────────────┐  │
│  │  Frontend     │     │  Backend (FastAPI)               │  │
│  │  React SPA    │────▶│                                  │  │
│  │  :5173        │     │  ┌────────┐ ┌────────┐          │  │
│  └──────────────┘     │  │  Auth   │ │ Events │          │  │
│                        │  │ Module │ │ Module │          │  │
│                        │  └────────┘ └────────┘          │  │
│                        │  ┌────────┐ ┌────────┐          │  │
│                        │  │Reports │ │ Users  │          │  │
│                        │  │ Module │ │ Module │          │  │
│                        │  └────────┘ └────────┘          │  │
│                        │  ┌──────────────┐               │  │
│                        │  │Notifications │               │  │
│                        │  │   Module     │               │  │
│                        │  └──────────────┘               │  │
│                        │  :8000                          │  │
│                        └──────┬──────────────┬───────────┘  │
│                               │              │              │
│                        ┌──────▼──────┐ ┌─────▼──────┐      │
│                        │ PostgreSQL  │ │   Redis    │      │
│                        │   :5432     │ │   :6379    │      │
│                        └─────────────┘ └────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Kubernetes Deployment (Implemented)

The system runs on Kubernetes today as a **horizontally scaled modular
monolith** — the whole backend is deployed as one image, run as many identical
replicas behind a load balancer. Manifests live in `k8s/`; see
[deployment.md](deployment.md) for the full procedure.

```
                    GKE Ingress (HTTP/S Load Balancer)
                       /                        \
                  /api  →                    /*  →
                       │                          │
              ┌────────▼────────┐        ┌────────▼────────┐
              │  backend Svc     │        │  frontend Svc    │
              │  Deployment+HPA  │        │  Deployment+HPA  │
              │  1–30 pods       │        │  1–10 pods       │
              │  FastAPI :8000   │        │  nginx :8080     │
              └────────┬────────┘        └─────────────────┘
                       │
          ┌────────────┴────────────┐
   ┌──────▼──────┐           ┌──────▼──────┐
   │ PostgreSQL  │           │   Redis     │
   │ StatefulSet │           │ Deployment  │
   └──────▲──────┘           └─────────────┘
          │
   ┌──────┴───────┐
   │ db-init Job  │  runs once: create tables + seed demo data
   └──────────────┘
```

Key cloud-native properties:

- **Stateless backend** — JWT auth, no server-side sessions → any replica can
  serve any request.
- **Run-once initialization** — schema creation and seeding happen in the
  `db-init` Job, never on pod startup, so replicas never race.
- **Health probes** — liveness (`/health`) is dependency-free; readiness
  (`/health/ready`) checks the database so traffic is held off pods that
  cannot serve.
- **Autoscaling** — HPA scales backend pods on CPU; the connection pool is
  sized per pod so `replicas x pool` stays under Postgres `max_connections`.
- **Zero-downtime rollouts** — RollingUpdate with `maxUnavailable: 0` plus a
  PodDisruptionBudget.

## Future Direction: Microservices Split

```
                         ┌─────────────┐
                         │   Ingress    │
                         │  Controller  │
                         └──────┬──────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
             ┌──────▼──────┐        ┌──────▼──────┐
             │   Frontend   │        │ API Gateway  │
             │   (Nginx)    │        │   (Kong)     │
             │  Deployment  │        │  Deployment  │
             └─────────────┘        └──────┬──────┘
                                           │
              ┌─────────────┬──────────────┼──────────────┬────────────────┐
              │             │              │              │                │
       ┌──────▼──────┐ ┌───▼───┐ ┌────────▼────┐ ┌──────▼──────┐ ┌──────▼──────┐
       │ Auth Service│ │Event  │ │Report Service│ │ User Service│ │Notification │
       │ Deployment  │ │Service│ │  Deployment  │ │ Deployment  │ │  Service    │
       │  + HPA      │ │+ HPA  │ │   + HPA      │ │  + HPA      │ │ Deployment  │
       └──────┬──────┘ └───┬───┘ └──────┬───────┘ └──────┬──────┘ └──────┬──────┘
              │            │            │                │                │
              └────────────┴────────┬───┴────────────────┘                │
                                    │                                     │
                             ┌──────▼──────┐                    ┌────────▼───────┐
                             │ PostgreSQL  │                    │   Message Queue │
                             │  (RDS/HA)   │                    │  (RabbitMQ)    │
                             └─────────────┘                    └────────────────┘
                                    │
                             ┌──────▼──────┐
                             │   Redis     │
                             │  (Cluster)  │
                             └─────────────┘
```

## Module Responsibilities

| Module | Current | Future Service | Responsibility |
|--------|---------|---------------|----------------|
| `auth` | Router + Service | Auth Service | JWT authentication, password verification |
| `events` | Router + Service | Event Service | CRUD for emergency events, lifecycle management |
| `reports` | Router + Service | Report Service | Safety status reporting, statistics aggregation |
| `users` | Router + Service | User Service | User CRUD, role management, org hierarchy |
| `notifications` | Router + Service | Notification Service | Reminder triggers, escalation tracking |

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | React 18 + TypeScript + Vite | Single Page Application |
| UI Framework | Tailwind CSS | Utility-first styling |
| Charts | Recharts | Data visualization |
| i18n | react-i18next | Multi-language (EN/zh-TW) |
| Backend | FastAPI (Python 3.12) | Async REST API |
| ORM | SQLAlchemy 2.0 (async) | Database access |
| Database | PostgreSQL 16 | Primary data store |
| Cache | Redis 7 | Caching and pub/sub |
| Auth | JWT (python-jose + bcrypt) | Stateless authentication |
| Container | Docker + Docker Compose | Container orchestration |

## Design Decisions

### 1. Monolith-First Approach
We chose a modular monolith over microservices for the initial prototype because:
- Faster development iteration
- Simpler deployment and debugging
- Clear module boundaries enable future splitting
- Industry best practice (Martin Fowler's "Monolith First")

### 2. Async-First Backend
FastAPI with async SQLAlchemy handles concurrent requests efficiently, critical during disaster events when many employees report simultaneously.

### 3. JWT Stateless Auth
Stateless tokens eliminate the need for session storage, making horizontal scaling straightforward.

### 4. Polling for Dashboard Refresh
The manager dashboard refreshes by polling the stats endpoints every 30
seconds. Polling keeps every request stateless — no sticky sessions, no
long-lived connections pinned to a pod — which is what makes the backend
trivially horizontally scalable. WebSocket/SSE push is a possible future
optimization but would add per-pod connection state.

### 5. Run-Once Database Initialization
Table creation and demo seeding run via `app.init_db` (Compose init service /
Kubernetes Job), never on application startup. Per-pod startup initialization
races across replicas; a single run-once job does not.

## Scalability Considerations

### Horizontal Scaling
- Backend is stateless → scales to N replicas behind a load balancer (HPA: 1–30)
- Connection pool sized per pod so `replicas x (pool_size + max_overflow)`
  stays under Postgres `max_connections`; pgbouncer for larger scale
- PostgreSQL supports read replicas for dashboard queries
- Redis can be clustered for cache distribution

### High Availability
- Kubernetes HPA auto-scales pods based on CPU/request metrics
- PostgreSQL with streaming replication for failover
- Redis Sentinel for automatic failover
- Zero-downtime deployments via rolling updates

### Performance Under Load
- Database connection pooling via SQLAlchemy
- Redis caching for frequently accessed stats
- Async I/O for non-blocking request handling
- Report aggregation queries use indexed columns
