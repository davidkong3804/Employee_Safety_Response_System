# Employee Safety & Response System

[![CI](https://github.com/davidkong3804/Employee_Safety_Response_System/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/davidkong3804/Employee_Safety_Response_System/actions/workflows/ci.yml)

**企業營運緊急事件安全回報系統**

A cloud-native emergency safety reporting system that enables enterprises to quickly assess employee safety status during critical incidents (earthquakes, fires, security breaches, etc.).

**Live demo**: <https://employee-safety.duckdns.org> — accounts `A001` / `M001` / `E001`, password `password123`.

## Features

| Role | Capabilities |
|------|-------------|
| **Employee** | One-tap safety reporting ("I'm Safe" / "Need Help"), view peer status |
| **Manager** | Real-time dashboard with charts, cross-facility filtering, send reminders to unreported employees |
| **Admin** | Event CRUD, user management, system-wide analytics |

- **Multi-language** — Toggle between 繁體中文 and English
- **Real-time Dashboard** — Pie/bar charts with auto-refresh every 30s
- **Role-based Access** — JWT authentication with 3 permission levels
- **Cloud-native Ready** — Docker Compose orchestration, modular monolith designed for microservice migration

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + Recharts |
| Backend | FastAPI (Python 3.12) + SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | JWT (python-jose + bcrypt) |
| i18n | react-i18next (EN / zh-TW) |
| Containers | Docker + Docker Compose |
| Orchestration | Kubernetes (GKE) — autoscaling, health probes, Ingress |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Docker Compose                     │
│                                                     │
│  ┌────────────┐    ┌──────────────────────────┐     │
│  │  Frontend   │───▶│  Backend (FastAPI)       │     │
│  │  React SPA  │    │  :8000                   │     │
│  │  :5173      │    │  ┌──────┐ ┌──────┐      │     │
│  └────────────┘    │  │ Auth │ │Events│      │     │
│                     │  └──────┘ └──────┘      │     │
│                     │  ┌──────┐ ┌──────┐      │     │
│                     │  │Report│ │Users │      │     │
│                     │  └──────┘ └──────┘      │     │
│                     │  ┌──────────────┐       │     │
│                     │  │Notifications │       │     │
│                     │  └──────────────┘       │     │
│                     └──────┬──────────┬───────┘     │
│                            │          │             │
│                     ┌──────▼───┐ ┌────▼─────┐      │
│                     │PostgreSQL│ │  Redis   │      │
│                     │  :5432   │ │  :6379   │      │
│                     └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────┘
```

Each backend module (`auth/`, `events/`, `reports/`, `users/`, `notifications/`) is self-contained with its own `router.py`, `schemas.py`, `models.py`, ready for future microservice extraction.

## Quick Start

### Prerequisites

- [Docker](https://www.docker.com/) & Docker Compose

### Run

```bash
# Clone the repository
git clone https://github.com/davidkong3804/Employee_Safety_Response_System.git
cd Employee_Safety_Response_System

# Start all services
docker compose up --build -d

# Check status
docker compose ps
```

Services will be available at:

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **Swagger Docs** | http://localhost:8000/docs |

### Demo Accounts

All accounts use password: `password123`

| Role | Employee ID | Name |
|------|------------|------|
| Admin | A001 | 廖唯辰 |
| Manager | M001 | 王建明 |
| Employee | E001 | 蔡明軒 |

> 38 users are automatically seeded across 5 departments, 2 facilities (Fab14, Fab18), with 2 events and mixed report statuses.

### Stop

```bash
docker compose down        # Stop services
docker compose down -v     # Stop and remove data volumes
```

### Deploy to Kubernetes (GKE)

```bash
kubectl apply -f k8s/
kubectl -n safety-system wait --for=condition=complete job/db-init --timeout=180s
```

Manifests in `k8s/` deploy the stack with horizontal autoscaling (backend
3–30 pods), health probes, and a GKE Ingress. See
[docs/deployment.md](docs/deployment.md) for the full procedure including
image build/push.

## Project Structure

```
├── docker-compose.yml              # Local container orchestration
├── k8s/                            # Kubernetes manifests (GKE)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 # FastAPI app + lifespan + health probes
│       ├── config.py               # Environment settings
│       ├── database.py             # Async SQLAlchemy engine + connection pool
│       ├── dependencies.py         # Auth guards (get_current_user, require_role)
│       ├── init_db.py              # Run-once: create tables (+ seed)
│       ├── seed.py                 # Demo data seeder
│       └── modules/
│           ├── auth/               # Login, JWT, profile
│           ├── events/             # Emergency event CRUD
│           ├── reports/            # Safety reporting + statistics
│           ├── users/              # User management
│           └── notifications/      # Reminder system
├── frontend/
│   ├── Dockerfile
│   └── src/
│       ├── pages/
│       │   ├── Login.tsx
│       │   ├── employee/           # Home, ReportPage, PeerStatus
│       │   ├── manager/            # Dashboard (charts + filters)
│       │   └── admin/              # EventManagement, UserManagement, Analytics
│       ├── api/                    # Axios API client
│       ├── components/             # Navbar, StatusBadge, ProtectedRoute
│       ├── contexts/               # AuthContext (JWT state)
│       └── i18n/                   # en.json, zh-TW.json
├── docs/
│   ├── architecture.md             # System architecture + K8s deployment
│   ├── deployment.md               # Docker Compose + GKE deployment guide
│   ├── er-diagram.md               # Database ER diagram (Mermaid)
│   ├── sequence-diagrams.md        # 6 sequence diagrams
│   ├── api-spec.md                 # Full API specification
│   └── user-stories.md             # 9 user stories + acceptance criteria
├── requirement.pdf
└── design_thinking.pdf
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | - | Login |
| GET | `/api/auth/me` | All | Get profile |
| GET | `/api/events` | All | List events |
| POST | `/api/events` | Admin | Create event |
| PATCH | `/api/events/{id}` | Admin | Update/close event |
| DELETE | `/api/events/{id}` | Admin | Delete event |
| POST | `/api/events/{id}/report` | All | Submit safety report |
| GET | `/api/events/{id}/stats` | Manager+ | Aggregated statistics |
| GET | `/api/events/{id}/stats/by-department` | Manager+ | Stats by department |
| GET | `/api/events/{id}/team-status` | Manager+ | Team member status |
| GET | `/api/events/{id}/all-status` | Admin | All employee status |
| POST | `/api/events/{id}/remind` | Manager+ | Trigger reminders |
| GET | `/api/users` | Manager+ | List users |
| POST | `/api/users` | Admin | Create user |

> Full interactive documentation at http://localhost:8000/docs

## Database Schema

4 tables: `users`, `events`, `safety_reports`, `reminders`

See [docs/er-diagram.md](docs/er-diagram.md) for full ER diagram.

## Documentation

| Document | Content |
|----------|---------|
| [Architecture](docs/architecture.md) | System architecture, tech decisions, K8s deployment |
| [Deployment](docs/deployment.md) | Docker Compose + GKE deployment, scaling, health probes |
| [ER Diagram](docs/er-diagram.md) | Database schema with Mermaid diagram |
| [Sequence Diagrams](docs/sequence-diagrams.md) | 6 key workflow diagrams |
| [API Specification](docs/api-spec.md) | Complete REST API reference |
| [User Stories](docs/user-stories.md) | 9 user stories with acceptance criteria |

## Design Thinking

Based on empathy maps for 3 personas:
1. **Fab Technician** — needs ultra-simple one-tap reporting under stress
2. **Department Manager** — needs real-time dashboard with auto-escalation
3. **System Admin** — needs reliable system that scales during disasters

See `design_thinking.pdf` for the full design thinking process.
