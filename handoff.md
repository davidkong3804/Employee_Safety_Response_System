# Handoff — 待辦事項

## 1. Manager / Admin 需能看見「需要協助」回報的備註

目前 `need_help` 狀態的員工可在 ReportPage 輸入備註（textarea），但 manager dashboard 與 admin all-status 視圖未顯示該備註。

- 後端：確認 `SafetyReport.message` 欄位有正確寫入 DB（從 `submit_report` 走 buffered/fallback 兩條路徑都要驗）
- 後端：team-status / all-status response 是否已回傳 `message`（看 `ReportResponse` schema）
- 前端：manager dashboard 的員工狀態列表、admin 的 all-status 表格，要展開或 hover 顯示「需要協助」者的備註
- 設計取捨：是否只在 `status === 'need_help'` 顯示？還是全部回報都顯示？
- 相關檔案：
  - `backend/app/modules/reports/router.py` (`get_team_status`, `get_all_status`, `_report_to_response`)
  - `backend/app/modules/reports/schemas.py` (`ReportResponse`)
  - `frontend/src/pages/manager/Dashboard.tsx`
  - `frontend/src/pages/admin/...`（all-status 視圖）

## 2. Manager 發送提醒應只送給「自己部門 + 尚未回報」的人

目前 `POST /api/events/{id}/remind` 對所有未回報用戶建立 `Reminder` row，沒有依呼叫者 role / 部門過濾。Manager 觸發時不應 spam 其他部門員工。

- 後端：在 `POST /api/events/{id}/remind` 加上：
  - 若 caller role 為 `manager` → 收件人限制為 `User.manager_id == current_user.id` 或 `SafetyReport.department_snapshot == current_user.department`（採用何者要與 team-status 過濾邏輯一致，參見 `get_team_status` L324-331 已用 `department_snapshot == current_user.department OR user_id == current_user.id`）
  - Admin 仍然全部送
- 收件人篩選必須與 manager 在 dashboard 看到的「未回報」清單完全一致，否則會出現「dashboard 上看不到的人也被提醒」
- 相關檔案：
  - `backend/app/modules/events/router.py`（remind endpoint）
  - 確認測試：`backend/tests/integration/test_events.py` 是否有 reminder 相關 cases，補 manager dept-scoped 與 admin all-scoped 的測試
