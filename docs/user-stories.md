# User Stories & Acceptance Criteria

## User Story Map

```
                    Employee (技術員)              Manager (課長)              Admin (管理員)
                   ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
   Core            │ US-1 一鍵回報安全  │       │ US-4 即時管理儀表板│       │ US-7 事件管理     │
   Features        │ US-2 醫療求助     │       │ US-5 自動催報提醒  │       │ US-8 使用者管理   │
                   │ US-3 同仁狀態確認  │       │ US-6 跨廠區篩選   │       │ US-9 系統分析     │
                   └──────────────────┘       └──────────────────┘       └──────────────────┘
```

---

## US-1: Quick Safety Report (一鍵回報安全)

**As a** fab technician trapped in a cleanroom during an emergency,
**I want to** report my safety status with a single tap,
**So that** my manager knows I'm safe and rescue resources can be directed to those who need help.

### Acceptance Criteria
- [x] Homepage displays active events with prominent "Report" button
- [x] Report page shows large "I'm Safe" (green) and "Need Help" (red) buttons
- [x] Single tap triggers the report submission
- [x] Response confirmation within 2 seconds
- [x] Report includes employee ID and timestamp automatically
- [x] Optional message field for additional details
- [ ] Offline mode: cache locally and auto-retry (future enhancement)

### Implementation
- **Frontend**: `src/pages/employee/ReportPage.tsx` - large circular buttons
- **Backend**: `POST /api/events/{id}/report`
- **Database**: Updates `safety_reports.status` and `reported_at`

---

## US-2: Medical Assistance Request (醫療求助)

**As a** technician who is injured during a disaster,
**I want to** quickly signal that I need medical help,
**So that** rescue teams can prioritize reaching me.

### Acceptance Criteria
- [x] "Need Help" button is visually distinct (red, smaller to prevent accidental taps)
- [x] Can attach a message describing the situation
- [x] Confirmation displayed after submission
- [ ] Anti-accidental-trigger (long-press or double-confirm) (future enhancement)
- [ ] Capture last-known location via Wi-Fi AP (future enhancement)
- [ ] Allow cancellation if accidentally triggered (future enhancement)

### Implementation
- **Frontend**: `src/pages/employee/ReportPage.tsx` - red button with message field
- **Backend**: Same endpoint with `status: "need_help"`

---

## US-3: Peer Status Confirmation (同仁狀態確認)

**As a** technician,
**I want to** see my teammates' safety status in real-time,
**So that** I can identify who might be missing and help locate them.

### Acceptance Criteria
- [x] View team member list with color-coded status (green=safe, red=help, gray=unreported)
- [x] Click member name to see contact info (phone number)
- [x] Sorted by urgency: need_help first, then unreported, then safe
- [ ] Support cross-facility assignment scenarios (future enhancement)

### Implementation
- **Frontend**: `src/pages/employee/PeerStatus.tsx`
- **Backend**: `GET /api/events/{id}/team-status`

---

## US-4: Real-time Management Dashboard (即時管理儀表板)

**As a** department manager,
**I want to** see an auto-summarized dashboard showing reported/unreported/need-help counts,
**So that** I can efficiently allocate resources to assist those in need.

### Acceptance Criteria
- [x] Visual pie chart showing safe/need_help/unreported distribution
- [x] Bar chart breaking down status by department
- [x] Color-coded employee list with sortable columns
- [x] Data auto-refreshes every 30 seconds
- [x] Summary cards showing total, safe, need_help, unreported counts
- [x] Report rate percentage displayed
- [ ] Graceful degradation under high load (future enhancement)

### Implementation
- **Frontend**: `src/pages/manager/Dashboard.tsx` with Recharts
- **Backend**: `GET /api/events/{id}/stats`, `GET /api/events/{id}/stats/by-department`

---

## US-5: Auto-escalation Reminders (自動催報提醒)

**As a** manager,
**I want to** send reminders to employees who haven't reported,
**So that** I can focus on immediate issues while the system handles follow-ups.

### Acceptance Criteria
- [x] "Send Reminders" button on dashboard
- [x] System counts unreported employees and sends reminders
- [x] Track reminder count and last contact time per employee
- [x] Display reminder confirmation with count
- [ ] Configurable time thresholds (15, 30, 60 min) (future enhancement)
- [ ] Multiple channels: push, SMS, voice call (future enhancement)
- [ ] Auto-exclude injured employees from reminders (future enhancement)

### Implementation
- **Frontend**: Dashboard page reminder button
- **Backend**: `POST /api/events/{id}/remind`
- **Database**: `reminders` table tracks escalation history

---

## US-6: Cross-facility Filtering (跨廠區篩選)

**As a** manager or admin,
**I want to** filter response data by facility and department,
**So that** I can prioritize resource allocation to the most affected areas.

### Acceptance Criteria
- [x] Dropdown filters for facility (Fab14, Fab18) and department
- [x] Employee table re-renders with filtered results
- [x] Filters apply to both table and summary statistics
- [ ] Permission control based on org hierarchy (future enhancement)
- [ ] Show "data unavailable" for offline facilities (future enhancement)

### Implementation
- **Frontend**: Dashboard filter dropdowns
- **Backend**: `GET /api/events/{id}/all-status?facility=X&department=Y`

---

## US-7: Event Management (事件管理)

**As a** system administrator,
**I want to** create and manage emergency events,
**So that** employees can be notified and begin reporting.

### Acceptance Criteria
- [x] Create event with title, description, type, and severity
- [x] Event creation auto-generates report records for all active employees
- [x] Close event (sets closed_at timestamp)
- [x] Delete event (cascades to reports and reminders)
- [x] Event list shows status badges (active/closed)

### Implementation
- **Frontend**: `src/pages/admin/EventManagement.tsx`
- **Backend**: Full CRUD on `/api/events`

---

## US-8: User Management (使用者管理)

**As a** system administrator,
**I want to** manage the employee directory,
**So that** new hires are included in safety reporting and departures are excluded.

### Acceptance Criteria
- [x] List all users with role/department/facility filters
- [x] Create new users with role assignment
- [x] Soft-delete (deactivate) users
- [x] Role badges (admin=purple, manager=blue, employee=gray)

### Implementation
- **Frontend**: `src/pages/admin/UserManagement.tsx`
- **Backend**: Full CRUD on `/api/users`

---

## US-9: System Analytics (系統分析)

**As a** system administrator,
**I want to** see overall system analytics across all events,
**So that** I can assess system effectiveness and improve emergency preparedness.

### Acceptance Criteria
- [x] Summary cards: total events, active events, average report rate, total employees
- [x] Bar chart: report status breakdown by event
- [x] Pie chart: overall status distribution across all events
- [ ] Response time metrics (future enhancement)
- [ ] Reminder effectiveness analysis (future enhancement)

### Implementation
- **Frontend**: `src/pages/admin/Analytics.tsx`
- **Backend**: Aggregated stats from multiple events
