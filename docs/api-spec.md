# API Specification

> Auto-generated interactive API docs available at: http://localhost:8000/docs (Swagger UI)

## Base URL
```
http://localhost:8000
```

## Authentication
All endpoints except `/api/auth/login` and `/health` require a Bearer token:
```
Authorization: Bearer <JWT_TOKEN>
```

---

## Auth Module

### POST /api/auth/login
Login and obtain JWT token.

**Request:**
```json
{
  "employee_id": "A001",
  "password": "password123"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Response 401:** Invalid credentials

### GET /api/auth/me
Get current user profile.

**Response 200:**
```json
{
  "id": "uuid",
  "employee_id": "A001",
  "name": "廖唯辰",
  "email": "liao.wc@tsmc.com",
  "role": "admin",
  "department": "資訊部",
  "facility": "Fab14",
  "phone": "0912-222-001"
}
```

---

## Events Module

### GET /api/events
List all events (active first, then by created_at desc).

**Auth:** Any authenticated user

### GET /api/events/{event_id}
Get a single event by ID.

**Auth:** Any authenticated user

**Response 200:**
```json
{
  "id": "uuid",
  "title": "2026-04-13 台南地震警報",
  "description": "...",
  "event_type": "earthquake",
  "severity": "high",
  "status": "active",
  "facility": "Fab14",
  "created_by": "uuid",
  "created_at": "2026-04-13T10:00:00Z",
  "closed_at": null
}
```

### POST /api/events
Create a new emergency event. Automatically generates safety_report records for active users in the affected facility (or all facilities if `facility` is omitted).

**Auth:** Admin only

**Request:**
```json
{
  "title": "2026-04-13 Earthquake",
  "description": "Please report your safety status immediately.",
  "event_type": "earthquake",
  "severity": "high",
  "facility": "Fab14"
}
```

> `facility` is optional. Omit or set to `null` to create a cross-facility event targeting all employees.

### PATCH /api/events/{event_id}
Update event details or close event.

**Auth:** Admin only

**Request:**
```json
{
  "status": "closed"
}
```

### DELETE /api/events/{event_id}
Delete event and all associated reports/reminders.

**Auth:** Admin only

---

## Reports Module

### POST /api/events/{event_id}/report
Submit safety report.

**Auth:** Any authenticated user

**Request:**
```json
{
  "status": "safe",
  "message": "I'm on the 3rd floor, all clear."
}
```

### GET /api/events/{event_id}/my-report
Get current user's report for this event.

**Auth:** Any authenticated user

### GET /api/events/{event_id}/stats
Get aggregated statistics.

**Auth:** Manager or Admin

**Response 200:**
```json
{
  "total": 38,
  "safe": 15,
  "need_help": 2,
  "unreported": 21,
  "report_rate": 44.7
}
```

### GET /api/events/{event_id}/stats/by-department
Get statistics grouped by department.

**Auth:** Manager or Admin

### GET /api/events/{event_id}/team-status
Get status of team members (manager sees subordinates, admin sees all).

**Auth:** Manager or Admin

### GET /api/events/{event_id}/all-status
Get all employees' status with optional facility/department filters.

**Auth:** Admin only

**Query params:** `?facility=Fab14&department=製造一部`

---

## Users Module

### GET /api/users
List users with optional filters.

**Auth:** Manager or Admin

**Query params:** `?role=employee&facility=Fab14&department=製造一部`

### POST /api/users
Create new user.

**Auth:** Admin only

### PATCH /api/users/{user_id}
Update user details.

**Auth:** Admin only

### DELETE /api/users/{user_id}
Soft-delete (deactivate) user.

**Auth:** Admin only

---

## Notifications Module

### POST /api/events/{event_id}/remind
Trigger reminders for all unreported employees.

**Auth:** Manager or Admin

**Response 200:**
```json
{
  "reminded_count": 21,
  "message": "Reminders sent to 21 unreported employee(s)"
}
```

### GET /api/events/{event_id}/reminders
Get reminder history for this event (who was reminded and how many times).

**Auth:** Manager or Admin

**Response 200:**
```json
[
  {
    "id": "uuid",
    "event_id": "uuid",
    "user_id": "uuid",
    "user_name": "蔡明軒",
    "employee_id": "E001",
    "reminder_count": 2,
    "last_reminded": "2026-04-13T10:30:00Z"
  }
]
```

---

## Health Check

### GET /health
```json
{
  "status": "healthy"
}
```

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Bad Request (invalid input) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient role) |
| 404 | Resource not found |
| 422 | Validation Error (Pydantic) |
| 500 | Internal Server Error |
