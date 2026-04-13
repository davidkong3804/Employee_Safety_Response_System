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

## Target Production Architecture (Kubernetes)

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

### 4. Server-Sent Events (SSE) for Real-time
SSE is simpler than WebSocket for one-way server-to-client updates, perfect for dashboard auto-refresh.

## Scalability Considerations

### Horizontal Scaling
- Backend is stateless → can scale to N replicas behind a load balancer
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
