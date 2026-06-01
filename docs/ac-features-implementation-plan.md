# Acceptance-Criteria Features + Dashboard Bug — Implementation Plan

Branch: `feature/safety-ac-features`. Goal: implement the 5 outstanding (red-marked) acceptance
criteria **without regressing stability**, each with unit/integration tests, plus fix the malignant
manager-dashboard blank-render bug. Work item-by-item; run tests after each.

Guiding rules:
- No schema migrations exist → schema changes mean updating models + `app.init_db` (the `db-init` Job
  recreates tables). Keep new columns **nullable with safe defaults** so existing rows/seed still load.
- Backend tests run with `CACHE_DISABLED=1`; `get_db`/`get_read_db` are overridden to the test session.
- Frontend tests: Vitest + Testing Library + MSW. Add/extend handlers for new endpoints.
- Locale-safe: all new UI strings go through i18n (`en.json` + `zh-TW.json`).

---

## 🐞 BUG-0 — Manager dashboard renders blank ("死白一片") on first mount

**Symptom:** Login as M001 → `/dashboard` blank; switching event and back, or Home→back, fixes it.

**ACTUAL ROOT CAUSE (confirmed by reproducing in-browser, not the ResponsiveContainer hypothesis):**
`Dashboard.tsx`'s init effect only selected an event when an *active* one existed:
`const active = evts.find(e => e.status === 'active'); if (active) setSelectedEventId(active.id)`.
When **no event is active** (all closed — exactly M001's current data), `selectedEventId` stayed `''`,
so `reloadAll` hit its `if (!selectedEventId) return` guard and never fetched → blank dashboard. The
`<select value="">` *looked* like it had a selection only because a controlled select whose value
matches no `<option>` falls back to showing the first option in the DOM (its `.value` even reports that
id), which is why "switch event and back" — a real `onChange` that sets a valid id — fixed it.
Verified: `GET /api/events` returned 4 events all `status:"closed"`; `/stats` etc. all returned 200.
**Not** a crash (no console error), **not** a ResponsiveContainer measuring issue.

**Fix (applied):** default to the most-recent event when none is active —
`const initial = evts.find(e => e.status === 'active') ?? evts[0]; if (initial) setSelectedEventId(initial.id)`.
The events list is ordered active-first then most-recent, so `evts[0]` is the natural default.

**Tests (done):** `frontend/src/__tests__/pages/Dashboard.test.tsx` — (1) no active event → falls back
to first event, fetches its stats, KPI numbers render; (2) prefers an active event when present; (3)
zero events → no stats fetch. All pass; full suite 92/92 green. Browser-verified the dashboard now
renders KPIs + charts + list on first mount.

---

## ✅ FEATURE-1 — 快速安全回報：回報內容含員工編號與當前時間戳記

**AC:** A submitted report must carry the employee_id and a current timestamp.
**Current state:** backend `ReportResponse` already returns `employee_id` + `reported_at`; the buffered
write stores `reported_at` (UTC now). Gap is likely the **employee-facing confirmation UI** not showing
them.
**Plan:**
- Backend: confirm `submit_report` always sets `reported_at = now_utc` and response includes
  `employee_id` (already true) — add an integration assertion to lock it in.
- Frontend (`ReportPage.tsx`): after a successful submit, show confirmation incl. employee_id +
  formatted timestamp (e.g. "已回報 · E001 · 2026-05-30 16:42").
**Tests:** integration `test_reports.py::test_submit_report_includes_employee_id_and_timestamp`;
frontend ReportPage test asserts the confirmation shows id + time.

---

## ✅ FEATURE-2 — 醫療協助請求：按鈕防呆(二次確認)避免誤觸

**AC:** The medical-assistance ("need_help") button needs a guard (long-press or double-confirm).
**Current state:** ReportPage submits need_help directly.
**Plan (frontend only):** intercept the need_help action with a confirmation modal ("確認需要協助?
此動作會立即通知主管" + Cancel/Confirm). Implement double-confirm (simplest, accessible) rather than
long-press. Reuse existing modal styling.
**Tests:** ReportPage test — clicking need_help opens the confirm dialog; submit only fires after
Confirm; Cancel aborts (no API call).

---

## ✅ FEATURE-3 — 管理儀表板:點擊圖表展開該分類員工名單

**AC:** Manager clicks a chart segment → employee list expands/filters to that category.
**Current state:** Dashboard has pie (safe/need_help/unreported) + bar (by dept) + a filterable list;
no click-through wiring.
**Plan (frontend, builds on BUG-0 fix):** add `onClick` to Pie cells (and optionally bar segments) →
sets `filterStatus` to the clicked category and scrolls to the list. Clicking the active slice again
clears the filter. Visual hint that the filter is active.
**Tests:** Dashboard test — clicking the "need_help" pie slice sets the status filter and the list
refetches with `status=need_help` (assert MSW query param / rendered rows).

---

## ✅ FEATURE-4 — 自動催促:管理者可設定觸發閾值(15/30/60 分鐘)

**AC:** Admin can configure the auto-reminder time threshold.
**Current state:** only manual `POST /events/{id}/remind`. No threshold, no scheduler.
**Plan (backend + frontend, most involved):**
- Model: add `Event.auto_remind_minutes: Mapped[int | None]` (nullable; null = off). Update
  `app.init_db`/seed defaults.
- Schema: add `auto_remind_minutes` to `EventCreate`/`EventUpdate`/`EventResponse` (validate ∈
  {15,30,60} or null).
- Scheduler: extend the existing background task (`app/background.py`) with a periodic sweep
  (e.g. every 60s): for each active event with `auto_remind_minutes` set, if
  `now - created_at >= threshold` and the unreported set hasn't been auto-reminded within the window,
  insert/increment `Reminder` rows for unreported users (reuse the manual-remind logic). Guard against
  duplicate sends using `Reminder.last_reminded`.
- Frontend (`pages/admin/EventManagement.tsx`): a 15/30/60/Off selector per event → PATCH event.
**Tests:** integration `test_events.py` — set `auto_remind_minutes`, simulate elapsed time (create
event with backdated `created_at` or call the sweep helper directly), assert reminders created for
unreported users only; validation rejects out-of-range values. Unit test for the sweep helper.

---

## ✅ FEATURE-5 — 跨廠區篩選:切換不同 Fab 廠區視角

**AC:** A dropdown/tabs lets a manager switch the Fab facility view (Fab14 / Fab18).
**Current state:** `all-status` accepts a `facility` filter; `stats` / `stats/by-department` /
`team-status` are not facility-scoped. Admin-only `all-status` already has it.
**Plan (backend + frontend):**
- Backend: add optional `facility` query param to `get_event_stats`, `get_stats_by_department`,
  `team-status` so the whole dashboard can be facility-scoped. Include `facility` in the stats cache
  key so scoped/unscoped don't collide.
- Frontend (Dashboard): a facility selector (All / Fab14 / Fab18) that passes `facility` into all
  dashboard fetches and re-renders within the AC's 3s.
**Tests:** integration — stats/team-status with `facility=Fab14` only counts that facility's snapshot
rows. Frontend — selecting a facility refetches with the param.

---

## Sequencing (low-risk → high-risk)
1. **BUG-0** (reproduce + fix + test) — unblocks the dashboard, prerequisite for F3/F5.
2. **FEATURE-2** (frontend-only confirm) — small, safe.
3. **FEATURE-1** (mostly verify + confirmation UI) — small.
4. **FEATURE-3** (chart click-through) — builds on BUG-0.
5. **FEATURE-5** (facility filter, backend+frontend).
6. **FEATURE-4** (auto-remind threshold + scheduler) — largest; schema + background + UI.

Each step: implement → add tests → run `pytest` (unit + relevant integration) and `pnpm vitest run` for
touched areas → only then move on. Commit per feature on this branch. Open a PR at the end (no direct
push to main).
