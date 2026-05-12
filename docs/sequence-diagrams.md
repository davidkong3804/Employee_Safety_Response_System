# Sequence Diagrams

## 1. User Login Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend as React SPA
    participant Backend as FastAPI
    participant DB as PostgreSQL

    User->>Frontend: Enter employee_id + password
    Frontend->>Backend: POST /api/auth/login
    Backend->>DB: SELECT user WHERE employee_id = ?
    DB-->>Backend: User record
    Backend->>Backend: bcrypt.checkpw(password, hash)
    alt Password valid
        Backend->>Backend: Create JWT token (exp: 8h)
        Backend-->>Frontend: 200 {access_token}
        Frontend->>Frontend: Store token in localStorage
        Frontend->>Backend: GET /api/auth/me (with Bearer token)
        Backend->>Backend: Decode JWT, extract user_id
        Backend->>DB: SELECT user WHERE id = ?
        DB-->>Backend: User profile
        Backend-->>Frontend: 200 {user profile with role}
        Frontend->>Frontend: Route based on role
    else Password invalid
        Backend-->>Frontend: 401 Unauthorized
        Frontend->>User: Show error message
    end
```

## 2. Emergency Event Creation Flow

```mermaid
sequenceDiagram
    actor Admin
    participant Frontend as React SPA
    participant Backend as FastAPI
    participant DB as PostgreSQL

    Admin->>Frontend: Fill event form (title, type, severity)
    Frontend->>Backend: POST /api/events (Admin JWT)
    Backend->>Backend: Verify JWT + role == admin
    Backend->>DB: INSERT INTO events (title, type, severity, facility, ...)
    DB-->>Backend: New event record

    alt facility is specified (e.g. "Fab14")
        Backend->>DB: SELECT * FROM users WHERE is_active = true AND facility = 'Fab14'
        DB-->>Backend: Fab14 users only
    else no facility (cross-facility event)
        Backend->>DB: SELECT * FROM users WHERE is_active = true
        DB-->>Backend: All active users (38 records)
    end

    loop For each matching user
        Backend->>DB: INSERT INTO safety_reports (event_id, user_id, status=NULL)
    end

    Backend-->>Frontend: 201 {event data}
    Frontend->>Admin: Show success, redirect to event list

    Note over Backend,DB: Only employees in the affected facility have "unreported" status
```

## 3. Employee Safety Report Flow (Core Use Case)

```mermaid
sequenceDiagram
    actor Employee
    participant Frontend as React SPA
    participant Backend as FastAPI
    participant DB as PostgreSQL

    Employee->>Frontend: Open active event
    Frontend->>Backend: GET /api/events/{id}/my-report
    Backend->>DB: SELECT report WHERE event_id AND user_id
    DB-->>Backend: Report (status: NULL)
    Backend-->>Frontend: {status: null} (unreported)
    Frontend->>Employee: Show "I'm Safe" + "Need Help" buttons

    Employee->>Frontend: Tap "I'm Safe" button
    Frontend->>Backend: POST /api/events/{id}/report {status: "safe"}
    Backend->>Backend: Verify JWT token
    Backend->>DB: UPDATE safety_reports SET status='safe', reported_at=NOW()
    DB-->>Backend: Updated report
    Backend-->>Frontend: 200 {updated report}
    Frontend->>Employee: Show success confirmation

    Note over Frontend: Response time < 2 seconds (per AC)
```

## 4. Manager Dashboard Flow

```mermaid
sequenceDiagram
    actor Manager
    participant Frontend as React SPA
    participant Backend as FastAPI
    participant DB as PostgreSQL

    Manager->>Frontend: Open Dashboard page
    Frontend->>Backend: GET /api/events (list all events)
    Backend-->>Frontend: Events list (select active one)

    par Parallel API calls
        Frontend->>Backend: GET /api/events/{id}/stats
        Backend->>DB: SELECT status, COUNT(*) GROUP BY status
        DB-->>Backend: {safe: 15, need_help: 2, unreported: 21}
        Backend-->>Frontend: EventStats

        Frontend->>Backend: GET /api/events/{id}/stats/by-department
        Backend->>DB: JOIN users + reports, GROUP BY department, status
        DB-->>Backend: Department breakdown
        Backend-->>Frontend: DepartmentStats[]

        Frontend->>Backend: GET /api/events/{id}/team-status
        Backend->>DB: SELECT reports WHERE user.manager_id = ?
        DB-->>Backend: Team reports
        Backend-->>Frontend: SafetyReport[]
    end

    Frontend->>Frontend: Render pie chart + bar chart + employee table
    Frontend->>Manager: Display dashboard

    loop Every 30 seconds (auto-refresh)
        Frontend->>Backend: Re-fetch stats + team-status
        Frontend->>Frontend: Update charts and table
    end
```

## 5. Reminder Trigger Flow

```mermaid
sequenceDiagram
    actor Manager
    participant Frontend as React SPA
    participant Backend as FastAPI
    participant DB as PostgreSQL

    Manager->>Frontend: Click "Send Reminders" button
    Frontend->>Backend: POST /api/events/{id}/remind

    Backend->>DB: SELECT reports WHERE event_id AND status IS NULL
    DB-->>Backend: Unreported employees list

    loop For each unreported employee
        Backend->>DB: SELECT reminder WHERE event_id AND user_id
        alt Reminder exists
            Backend->>DB: UPDATE reminder SET count+1, last_reminded=NOW()
        else No reminder yet
            Backend->>DB: INSERT reminder (count=1, last_reminded=NOW())
        end
    end

    Backend-->>Frontend: {reminded_count: 21, message: "..."}
    Frontend->>Manager: Toast "已發送 21 則提醒"

    Note over Backend: In production, this would trigger<br/>push notifications, SMS, or voice calls<br/>via external notification service
```

## 6. Cross-Facility Filtering Flow

```mermaid
sequenceDiagram
    actor Admin
    participant Frontend as React SPA
    participant Backend as FastAPI
    participant DB as PostgreSQL

    Admin->>Frontend: Select facility filter "Fab14"
    Frontend->>Backend: GET /api/events/{id}/all-status?facility=Fab14
    Backend->>DB: SELECT reports JOIN users WHERE facility='Fab14'
    DB-->>Backend: Filtered reports
    Backend-->>Frontend: SafetyReport[] (Fab14 only)
    Frontend->>Frontend: Re-render employee table
    Frontend->>Admin: Show filtered results

    Note over Frontend: Filter response < 3 seconds (per AC)
```
