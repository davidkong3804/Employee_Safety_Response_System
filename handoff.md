# Handoff — 待辦事項

✅ **兩項皆已完成（2026-05-26）**，保留紀錄做 audit trail。

## 1. Manager / Admin 需能看見「需要協助」回報的備註 — ✅ Done

Manager Dashboard 加「備註」欄位（manager / admin 共用同一 page），row 內 truncate + 原生 hover tooltip 顯示完整訊息；`status === 'need_help'` 顯紅色加粗。Backend `ReportResponse.message` 本來就已 expose，不需動。

修改檔案：
- `frontend/src/pages/manager/Dashboard.tsx`（grid 加第 7 欄、ReportRow 加 message cell）
- `frontend/src/i18n/zh-TW.json` + `en.json`（新增 `dashboard.note`）

## 2. Manager 發送提醒應只送給「自己部門 + 尚未回報」的人 — ✅ Done

`POST /api/events/{id}/remind` 加 role-aware filter：admin 維持全事件範圍；manager 限制 `SafetyReport.department_snapshot == current_user.department`，與 `get_team_status` 的篩選一致（用 snapshot 而非 live `user.department`，避免轉部門的員工被歷史事件 reminder 漏抓）。

修改檔案：
- `backend/app/modules/notifications/router.py`（`trigger_reminders` 加 dept filter）
- `backend/tests/integration/test_notifications.py`（更新 4 個既有 test 預期值，rename `test_all_unreported_users_get_reminded` → `test_manager_reminds_own_department_unreported`，新增 `test_admin_reminds_across_all_departments` 鎖住 admin 不被 scope）
