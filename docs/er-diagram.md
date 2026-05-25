# Entity-Relationship Diagram

## ER Diagram (Mermaid)

```mermaid
erDiagram
    USERS {
        uuid id PK
        varchar(20) employee_id UK "e.g. E001, M001, A001"
        varchar(100) name
        varchar(200) email UK
        varchar(200) password_hash
        enum role "employee | manager | admin"
        varchar(100) department "e.g. 製造一部"
        varchar(50) facility "e.g. Fab14, Fab18"
        varchar(20) phone
        uuid manager_id FK "self-reference"
        boolean is_active "soft delete"
        timestamp created_at
    }

    EVENTS {
        uuid id PK
        varchar(200) title "e.g. 2026-04-13 台南地震警報"
        text description
        varchar(50) event_type "earthquake | fire | flood | security | other"
        enum severity "low | medium | high | critical"
        enum status "active | closed"
        varchar50_array facility "ARRAY of fab codes; NULL = all facilities"
        uuid created_by FK
        timestamp created_at
        timestamp closed_at
    }

    SAFETY_REPORTS {
        uuid id PK
        uuid event_id FK
        uuid user_id FK
        enum status "safe | need_help | NULL(unreported)"
        text message "optional detail"
        timestamp reported_at
        timestamp created_at
    }

    REMINDERS {
        uuid id PK
        uuid event_id FK
        uuid user_id FK
        integer reminder_count
        timestamp last_reminded
        timestamp created_at
    }

    USERS ||--o{ USERS : "manages (manager_id)"
    USERS ||--o{ EVENTS : "creates (created_by)"
    USERS ||--o{ SAFETY_REPORTS : "reports (user_id)"
    USERS ||--o{ REMINDERS : "receives (user_id)"
    EVENTS ||--o{ SAFETY_REPORTS : "has (event_id)"
    EVENTS ||--o{ REMINDERS : "triggers (event_id)"
```

## Table Details

### users
The central entity representing all system users across three roles.
- **Self-referential FK**: `manager_id` references `users.id`, enabling org hierarchy.
- **Soft delete**: `is_active = false` instead of actual deletion preserves historical data.
- **Indexes**: `employee_id` (unique), `email` (unique), `manager_id`, `(department, facility)`

### events
Emergency events created by administrators.
- **Lifecycle**: `active` → `closed` (sets `closed_at` timestamp)
- **Types**: earthquake, fire, flood, security, other
- **Facility scoping**: `facility` is a Postgres `VARCHAR(50)[]` (`ARRAY(String(50))` in SQLAlchemy). Holds the fab codes affected by the event (e.g. `['Fab14', 'Fab18']`). `NULL` / empty means **all facilities** — the event is global.
- **On creation**: automatically generates one `safety_report` placeholder per active user; if `facility` is non-empty, only users whose `User.facility` is in that list get a placeholder.

### safety_reports
Core reporting table with one record per user per event.
- **Unique constraint**: `(event_id, user_id)` — each user can only have one report per event
- **Status lifecycle**: `NULL` (unreported) → `safe` or `need_help`
- **Indexes**: `(event_id, status)` for dashboard aggregation queries

### reminders
Tracks notification attempts for unreported employees.
- **Increment pattern**: each reminder trigger increments `reminder_count` and updates `last_reminded`
- Enables tracking escalation frequency per employee

## Key Queries

### Dashboard Stats (most frequent query)
```sql
SELECT status, COUNT(*)
FROM safety_reports
WHERE event_id = :event_id
GROUP BY status;
```

### Department Breakdown
```sql
SELECT u.department, sr.status, COUNT(*)
FROM safety_reports sr
JOIN users u ON sr.user_id = u.id
WHERE sr.event_id = :event_id
GROUP BY u.department, sr.status;
```

### Manager's Team Status
```sql
SELECT sr.*, u.name, u.employee_id, u.department
FROM safety_reports sr
JOIN users u ON sr.user_id = u.id
WHERE sr.event_id = :event_id
AND (u.manager_id = :manager_id OR u.id = :manager_id);
```
