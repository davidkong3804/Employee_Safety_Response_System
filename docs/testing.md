# Testing Guide

**Employee Safety & Response System — 測試與 CI/CD 完整說明**

---

## 目錄

1. [測試架構總覽](#1-測試架構總覽)
2. [環境需求](#2-環境需求)
3. [後端單元測試 (Unit Tests)](#3-後端單元測試-unit-tests)
4. [後端整合測試 (Integration Tests)](#4-後端整合測試-integration-tests)
5. [前端單元測試 (Frontend Unit Tests)](#5-前端單元測試-frontend-unit-tests)
6. [E2E 端對端測試 (Playwright)](#6-e2e-端對端測試-playwright)
7. [性能測試 (Locust)](#7-性能測試-locust)
8. [CI/CD Pipeline (GitHub Actions)](#8-cicd-pipeline-github-actions)
9. [測試設計決策](#9-測試設計決策)
10. [撰寫新測試指南](#10-撰寫新測試指南)
11. [常見問題 (FAQ)](#11-常見問題-faq)

---

## 1. 測試架構總覽

系統採用四層測試金字塔：

```
                    ┌─────────────────┐
                    │   E2E Tests     │  ← Playwright (4 spec files)
                    │  (真實瀏覽器)    │     ~5 min
                    └────────┬────────┘
               ┌─────────────┴──────────────┐
               │    Integration Tests        │  ← pytest + real PostgreSQL
               │   (真實 HTTP + 真實 DB)     │     7 modules, ~3 min
               └─────────────┬──────────────┘
          ┌───────────────────┴───────────────────┐
          │           Unit Tests                   │  ← pytest (backend) + Vitest (frontend)
          │    (純邏輯，不依賴外部服務)              │     ~1 min each
          └───────────────────────────────────────┘
```

```
                    ┌─────────────────┐
                    │ Performance     │  ← Locust (手動執行，不在 CI)
                    │  Tests          │
                    └─────────────────┘
```

### 測試檔案分布

```
├── backend/
│   ├── pytest.ini                          # pytest 全域設定
│   └── tests/
│       ├── conftest.py                     # 共用 fixtures（engine, session, client, users）
│       ├── unit/
│       │   ├── test_auth_utils.py          # hash_password, verify_password, JWT
│       │   ├── test_schemas.py             # Pydantic schema 驗證
│       │   └── test_dependencies.py        # require_role() 邏輯
│       └── integration/
│           ├── test_health.py              # GET /health
│           ├── test_auth.py               # POST /api/auth/login, GET /api/auth/me
│           ├── test_events.py             # Events CRUD + 核心業務邏輯
│           ├── test_reports.py            # 回報提交 + 統計計算
│           ├── test_users.py              # Users CRUD + soft delete
│           ├── test_notifications.py      # 提醒觸發 + 計數
│           └── test_rbac.py              # 全部 endpoint × 三種角色矩陣
│
├── frontend/
│   └── src/
│       ├── vitest.setup.ts                # jsdom + i18n + localStorage 清除
│       └── __tests__/
│           ├── components/
│           │   ├── StatusBadge.test.tsx       # Badge 渲染 + CSS class
│           │   ├── ProtectedRoute.test.tsx    # 路由保護邏輯
│           │   ├── FacilitySelector.test.tsx  # 多選廠區 UX：全廠區 toggle、國家展開、disabled
│           │   └── Navbar.test.tsx            # 角色 nav 連結可見性 + 登出
│           ├── contexts/
│           │   └── AuthContext.test.tsx   # login/logout/init/401 recovery
│           ├── api/
│           │   ├── auth.test.ts           # login() / getMe()
│           │   ├── client.test.ts         # axios interceptors
│           │   ├── events.test.ts         # list/get/create/update/delete + facility 陣列
│           │   ├── users.test.ts          # list (含 filters) + CRUD
│           │   └── reports.test.ts        # 7 個 endpoint，含 query string 拼接
│           └── pages/
│               ├── Login.test.tsx         # 表單、登入後依角色 redirect、錯誤 toast
│               └── ReportPage.test.tsx    # 一鍵回報核心流程、已回報視圖
│
└── tests/
    ├── e2e/
    │   ├── playwright.config.ts
    │   ├── fixtures/
    │   │   └── auth.fixture.ts            # adminPage, managerPage, employeePage
    │   └── specs/
    │       ├── auth.spec.ts               # 登入頁面、驗證流程
    │       ├── employee-workflow.spec.ts   # 員工操作流程
    │       ├── manager-workflow.spec.ts    # 主管操作流程
    │       └── admin-workflow.spec.ts      # 管理員完整事件生命週期
    └── performance/
        └── locustfile.py                  # 三種角色負載情境
```

---

## 2. 環境需求

### 後端測試

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | 3.12 | 執行環境 |
| pytest | 8.3.4 | 測試框架 |
| pytest-asyncio | 0.24.0 | 非同步測試支援 |
| pytest-cov | 6.0.0 | 覆蓋率報告 |
| httpx | 0.28.1 | ASGI 測試客戶端 |
| PostgreSQL | 16 | Integration tests 用 DB |

> **Unit tests 不需要 PostgreSQL**，只有 integration tests 需要。

### 前端測試

| 工具 | 版本 | 用途 |
|------|------|------|
| Node.js | 18+ | 執行環境 |
| pnpm | 10+ | 套件管理 |
| Vitest | 2.1.9 | 測試框架 |
| jsdom | 24.x | 瀏覽器模擬環境 |
| @testing-library/react | 16.x | React 元件測試 |
| @testing-library/jest-dom | 6.x | DOM 斷言擴充 |

### E2E 測試

| 工具 | 版本 | 用途 |
|------|------|------|
| Playwright | 1.49+ | 瀏覽器自動化 |
| Chromium | — | 測試瀏覽器 |
| 完整 Docker stack | — | 需要前後端全部啟動 |

### 性能測試

| 工具 | 用途 |
|------|------|
| Locust | HTTP 負載測試 |
| 完整 Docker stack + seed data | 需要 38 筆真實使用者資料 |

---

## 3. 後端單元測試 (Unit Tests)

Unit tests **不需要資料庫**，執行速度最快。

### 快速執行

```bash
cd backend
pytest tests/unit/ -v
```

### 測試內容

#### `test_auth_utils.py` — 認證工具函式

測試 `app/modules/auth/router.py` 中的三個純函式：

| 函式 | 測試重點 |
|------|---------|
| `hash_password()` | 輸出 `$2b$` bcrypt 格式；每次 salt 不同 |
| `verify_password()` | 正確密碼回傳 True；錯誤/空密碼回傳 False |
| `create_access_token()` | payload 含 `sub` + `exp`；正確過期時間；過期/竄改 token 拋 JWTError |

#### `test_schemas.py` — Pydantic 資料驗證

驗證所有 Request/Response schema 的欄位強制規則：

| Schema | 關鍵驗證 |
|--------|---------|
| `LoginRequest` | `employee_id` 和 `password` 皆為必填 |
| `EventCreate` | `title`, `event_type`, `severity` 必填；`description` 可選 |
| `EventUpdate` | 所有欄位皆為選填（部分更新） |
| `ReportSubmit` | `status` 必填（字串，業務邏輯另行驗證值域） |
| `UserCreate` | 五個必填欄位；`manager_id` 預設 None |
| `UserUpdate` | 所有欄位皆選填 |

#### `test_dependencies.py` — 角色存取控制

直接呼叫 `require_role()` 回傳的 coroutine，不需要 HTTP layer：

- 允許的角色 → 回傳 user 物件
- 不允許的角色 → 拋 `HTTPException(403, "Insufficient permissions")`

### 執行選項

```bash
# 只跑 unit tests
pytest tests/unit/ -v

# 顯示測試覆蓋率
pytest tests/unit/ --cov=app --cov-report=term-missing

# 用標記過濾
pytest -m unit
```

---

## 4. 後端整合測試 (Integration Tests)

Integration tests 使用**真實 PostgreSQL**，驗證完整的 HTTP 請求 → 業務邏輯 → 資料庫寫入流程。

### 前置設定：建立測試資料庫

```bash
# 方式一：若本機已有 PostgreSQL
createdb -U app safety_response_test

# 方式二：用 Docker 啟動獨立測試 DB（port 5433，不影響開發 DB）
docker compose -f docker-compose.test.yml up db-test -d
```

### 執行

```bash
cd backend

# 設定測試 DB URL（也可寫入 .env.test）
export TEST_DATABASE_URL=postgresql+asyncpg://app:devpassword@localhost:5432/safety_response_test

# 執行所有 integration tests
pytest tests/integration/ -v

# 同時產生覆蓋率報告
pytest tests/integration/ -v --cov=app --cov-report=html:htmlcov

# 只跑特定模組
pytest tests/integration/test_events.py -v

# 只跑特定測試
pytest tests/integration/test_events.py::TestCreateEvent::test_create_event_generates_reports_for_every_active_user -v
```

### Fixture 架構

`conftest.py` 使用 **connection-level transaction rollback** 確保每個測試互相隔離：

```
test_engine (scope=session)
    ↓ drop_all → create_all（整個測試 session 只做一次）
    
db_session (scope=function)
    ↓ 開啟一個 connection + 開始 transaction
    ↓ 測試執行（所有 SQL 在 transaction 內）
    ↓ rollback（DB 恢復乾淨狀態）
    
client (scope=function)
    ↓ 覆寫 get_db → 回傳同一個 db_session
    ↓ AsyncClient 直接測試 ASGI app（不需啟動真實 HTTP server）
    ↓ 測試後清除 dependency_overrides
```

**重要**：`main.py` 的 `lifespan`（含 `seed_data()`）被替換為 no-op，確保 seed data 不會污染測試 DB。

### 可用的 Fixtures

| Fixture | Scope | 說明 |
|---------|-------|------|
| `test_engine` | session | 測試 DB 的 AsyncEngine |
| `db_session` | function | 帶 rollback 隔離的 AsyncSession |
| `client` | function | 注入 db_session 的 AsyncClient |
| `admin_user` | function | role=admin 的 User 物件 |
| `manager_user` | function | role=manager 的 User 物件 |
| `employee_user` | function | role=employee，manager_id 指向 manager_user |
| `admin_headers` | function | `{"Authorization": "Bearer <admin_jwt>"}` |
| `manager_headers` | function | `{"Authorization": "Bearer <manager_jwt>"}` |
| `employee_headers` | function | `{"Authorization": "Bearer <employee_jwt>"}` |
| `active_event` | function | active 事件 + 三筆 placeholder SafetyReport |

### 測試模組說明

#### `test_events.py` — 核心業務邏輯（最重要）

| 測試 | 驗證重點 |
|------|---------|
| `test_create_event_generates_reports_for_every_active_user` | 建立事件時，自動為所有 `is_active=True` 的 user 建立 placeholder |
| `test_inactive_user_excluded_from_auto_reports` | `is_active=False` 的 user 不產生 placeholder |
| `test_delete_cascades_reports_and_reminders` | 刪除事件時，關聯的 safety_reports 和 reminders 也被清除 |
| `test_closing_event_sets_closed_at` | PATCH status=closed 時，`closed_at` 自動填入 |
| `test_active_events_come_before_closed` | 事件列表排序：active 在前，closed 在後 |
| RBAC 測試 | Manager/Employee 無法 POST/PATCH/DELETE events（回傳 403） |

#### `test_reports.py` — 回報與統計

| 測試 | 驗證重點 |
|------|---------|
| `test_submit_safe_report` | `reported_at` 自動填入；`user_id` 正確 |
| `test_resubmit_updates_existing_report` | 重複提交會更新現有記錄，不會產生新記錄 |
| `test_initial_stats_all_unreported` | total=3, safe=0, unreported=3, report_rate=0.0 |
| `test_stats_after_one_safe_report` | report_rate 計算正確（≈33.3%） |
| `test_manager_sees_only_subordinates_and_self` | 主管只看到自己的下屬，看不到其他主管的下屬 |
| `test_admin_sees_all_reports` | 管理員的 team-status 看到全部 user |
| `test_filter_by_facility` | facility 過濾查詢正確運作 |

#### `test_notifications.py` — 提醒系統

| 測試 | 驗證重點 |
|------|---------|
| `test_all_unreported_users_get_reminded` | 首次提醒：reminded_count 等於未回報人數 |
| `test_excludes_already_reported_users` | 已回報的 user 不列入提醒對象 |
| `test_reminder_count_increments_on_repeat` | 重複提醒：reminder_count 累加（1 → 2） |

#### `test_rbac.py` — 角色權限矩陣

使用 `@pytest.mark.parametrize` 對 **13 個 endpoint × 3 種角色**進行系統化驗證：

- **應該被拒絕的角色** → 確認回傳 403
- **應該被允許的角色** → 確認不回傳 403 或 401（可能回傳 404，因為使用 fake UUID）

> 403 在 DB 查詢之前就會回傳，所以使用 fake UUID 即可測試 RBAC，不需要真實存在的資源。

---

## 5. 前端單元測試 (Frontend Unit Tests)

### 執行

```bash
cd frontend

# 執行一次（CI 模式）
pnpm vitest run

# 監看模式（開發時使用）
pnpm vitest

# 產生覆蓋率報告
pnpm vitest run --coverage
# → 報告在 frontend/coverage/index.html
```

### 測試設定

`vite.config.ts` 中的 `test` 設定：

```typescript
test: {
  globals: true,          // 不需要 import describe/it/expect
  environment: 'jsdom',   // 模擬瀏覽器環境
  setupFiles: './src/vitest.setup.ts',  // 全域設定
  coverage: {
    provider: 'v8',
    reporter: ['text', 'html', 'lcov'],
    include: ['src/**/*.{ts,tsx}'],
  },
}
```

`vitest.setup.ts` 在每個測試前後執行：
- 初始化 i18next（提供 `status.safe`、`status.need_help` 等翻譯鍵值）
- 每個測試後：清除 DOM (`cleanup()`)、清除 `localStorage`、清除所有 mock

### 測試模組說明

#### `StatusBadge.test.tsx`

| 測試 | 驗證 |
|------|------|
| `safe` 狀態 | 文字 "Safe"；`bg-green-100 text-green-800` CSS class |
| `need_help` 狀態 | 文字 "Need Help"；`bg-red-100` CSS class |
| `null` 狀態（未回報） | 文字 "Unreported"；`bg-gray-100` CSS class |
| `size="sm"`（預設） | `px-2 py-0.5 text-xs` CSS class |
| `size="md"` | `px-3 py-1.5 text-sm` CSS class |
| 元素類型 | 渲染為 `<span>` |

#### `ProtectedRoute.test.tsx`

使用 `vi.spyOn(AuthContextModule, 'useAuth')` mock 認證狀態：

| 情境 | 預期行為 |
|------|---------|
| `loading=true` | 顯示 `.animate-spin` 載入動畫 |
| `user=null` | Redirect 到 `/login` |
| 已登入 + 無角色限制 | 渲染 `children` |
| 已登入 + 角色符合 | 渲染 `children` |
| 已登入 + 角色不符 | Redirect 到 `/` |

#### `AuthContext.test.tsx`

使用 `vi.mock('../../api/auth')` mock API 層：

| 情境 | 驗證 |
|------|------|
| 初始化有 token | 呼叫 `getMe()`，loading 變 false，設定 user |
| 初始化無 token | 不呼叫 `getMe()`，loading 變 false，user 為 null |
| 初始化 token 失效（401） | 清除 localStorage token，user 為 null |
| `login()` | 儲存 token 到 localStorage，設定 user |
| `logout()` | 清除 localStorage token，user 設為 null |

#### `auth.test.ts` / `client.test.ts`

驗證 axios instance 的 interceptor 行為：
- Request interceptor：有 token → 注入 `Authorization: Bearer <token>` header
- Request interceptor：無 token → 不加 header
- Response interceptor：收到 401 → 清除 localStorage token

#### `events.test.ts` / `users.test.ts` / `reports.test.ts`

`vi.mock('../../api/client')` 取代 axios，僅驗證**呼叫合約**（method、path、payload）：

| API client | 驗證重點 |
|------------|---------|
| `events.test.ts` | `listEvents` / `getEvent` / `createEvent`（含 `facility: string[]`）/ `updateEvent` / `deleteEvent` 對應 RESTful 路徑 |
| `users.test.ts` | `listUsers` 三種 filter 組合（無、單一 role、facility+department）正確以 `params` 帶入 |
| `reports.test.ts` | 7 個 endpoint；`getAllStatus` 用 `URLSearchParams` 拼接 `?facility=X&department=Y` 的順序正確 |

#### `FacilitySelector.test.tsx`

複雜 UX 元件（國家→地區→廠區三層階層 + 全廠區 master toggle）的核心互動：

| 測試類別 | 驗證 |
|---------|------|
| 初始 render | 全廠區、四個國家、預設不展開、預設 `isAll=true`（value=[]）|
| 全廠區 toggle | 勾起 → `onChange(allFabs)`；勾掉 → `onChange([])` |
| 國家展開 | 點 Taiwan 顯示 Hsinchu / Miaoli / Zhunan...；fabs 數量 badge 顯示 `(11 fabs)` |
| 顯式 fab 勾選 | 加入 fab → onChange 收到新陣列；取消 → onChange 收到 filter 後的陣列 |
| disabled 邏輯 | `isAll=true` 時，子層 fab 勾選框 checked + disabled |

#### `Navbar.test.tsx`

依角色顯示 nav 連結：

| 角色 | 應該看到 | 不該看到 |
|------|---------|---------|
| 未登入 | 整個 Navbar 不 render | — |
| employee | Home | Dashboard / Event / User Management |
| manager | Home / Dashboard | Event / User Management |
| admin | Home / Dashboard / Event / User Management | — |

外加：點 logout 按鈕呼叫 `logout()` 並 `navigate('/login')`；user name + role 正確顯示。

#### `Login.test.tsx`

`vi.spyOn(useAuth)` 注入 mock `login()`，`vi.mock('react-hot-toast')` 攔 toast：

| 情境 | 驗證 |
|------|------|
| 表單 render | Employee ID / Password 兩個 placeholder + Login 按鈕 |
| admin 登入 | navigate(`/admin/events`) |
| manager 登入 | navigate(`/dashboard`) |
| employee 登入 | navigate(`/`) |
| 登入失敗 | `toast.error('Invalid employee ID or password')`，不 navigate |
| 憑證傳遞 | `login(employeeId, password)` 收到使用者輸入的值 |

#### `ReportPage.test.tsx`

`vi.mock` 掉 `api/events` / `api/reports` / `react-hot-toast`，覆蓋核心 US-1 流程：

| 情境 | 驗證 |
|------|------|
| 未回報視圖 | "I'm Safe" 與 "Need Help" 兩顆大按鈕 + textarea + event title |
| 點 "I'm Safe" | `submitReport(eventId, { status: 'safe', message: undefined })` + 成功 toast |
| 點 "Need Help" | `submitReport(eventId, { status: 'need_help', ... })` |
| 訊息傳遞 | 在 textarea 輸入後再送出，message 一併傳入 |
| 送出失敗 | `toast.error('Report failed, please retry')` |
| 已回報視圖 | 顯示「You have already reported」+ 過往 message；隱藏兩顆按鈕 |

---

## 6. E2E 端對端測試 (Playwright)

E2E tests 需要**完整的系統啟動**（前端 + 後端 + 資料庫 + seed data）。

### 前置步驟

```bash
# 1. 啟動完整 stack
docker compose up -d --build

# 2. 等待後端健康檢查通過
curl http://localhost:8000/health

# 3. 安裝 Playwright 與 Chromium（只需第一次）
cd tests/e2e
npm install
npx playwright install chromium
```

### 執行

```bash
cd tests/e2e

# 執行全部 E2E tests（無頭模式）
npx playwright test

# 顯示瀏覽器（有頭模式，方便除錯）
npx playwright test --headed

# 只跑特定 spec
npx playwright test specs/admin-workflow.spec.ts

# 產生 HTML 報告
npx playwright test --reporter=html
npx playwright show-report playwright-report
```

### Auth Fixtures

`fixtures/auth.fixture.ts` 提供三個已登入的 browser context：

```typescript
import { test, expect } from '../fixtures/auth.fixture'

test('admin can do something', async ({ adminPage }) => {
  await adminPage.goto('/admin/events')
  // adminPage 已以 A001 身份登入
})
```

| Fixture | 登入帳號 | 角色 |
|---------|---------|------|
| `adminPage` | A001 | admin |
| `managerPage` | M001 | manager |
| `employeePage` | E001 | employee |

每個 fixture 使用獨立的 browser context（不共用 localStorage/cookies），確保測試互不干擾。

### E2E 測試說明

#### `auth.spec.ts`
- 登入頁面元素渲染正確
- 有效 admin 憑證登入後離開 `/login`
- 無效憑證顯示錯誤 toast
- 未登入存取受保護路由 → 重定向 `/login`

#### `admin-workflow.spec.ts`（最完整的 E2E）
1. Admin 可存取 Event Management 頁面
2. Admin 可存取 User Management 頁面
3. 完整事件生命週期：建立事件 → 出現在列表 → 關閉 → 刪除

#### `employee-workflow.spec.ts`
- 員工首頁正常載入
- 員工無法存取 `/admin/events`（角色保護有效）
- 員工無法存取 `/admin/users`（角色保護有效）
- 登出後重定向 `/login`

#### `manager-workflow.spec.ts`
- 主管可存取 Dashboard
- 主管無法存取 User Management（角色保護有效）

---

## 7. 性能測試 (Locust)

性能測試**不在 CI 中自動執行**，需手動在本機或專用環境運行。

### 前置需求

```bash
pip install locust

# 需要已啟動的 stack（含 seed data）
docker compose up -d
```

### 情境一：正常負載（模擬真實使用）

模擬 seed data 的 30 位員工 + 5 位主管 + 3 位管理員（38 人）：

```bash
locust -f tests/performance/locustfile.py \
  --headless \
  --host http://localhost:8000 \
  --users 38 \
  --spawn-rate 5 \
  --run-time 60s \
  --html tests/performance/reports/normal_$(date +%Y%m%d_%H%M%S).html
```

### 情境二：壓力測試（超載情境）

```bash
locust -f tests/performance/locustfile.py \
  --headless \
  --host http://localhost:8000 \
  --users 100 \
  --spawn-rate 20 \
  --run-time 120s \
  --html tests/performance/reports/stress_$(date +%Y%m%d_%H%M%S).html
```

### 情境三：互動式 Web UI

```bash
locust -f tests/performance/locustfile.py --host http://localhost:8000
# → 開啟 http://localhost:8089 進行互動調整
```

### User 類型與行為

| 類型 | Weight | 主要行為 |
|------|--------|---------|
| `EmployeeUser` | 30 | GET /events (×5), POST /report (×3), GET /my-report (×2), GET /health (×1) |
| `ManagerUser` | 5 | GET /team-status (×3), GET /stats (×2), POST /remind (×1) |
| `AdminUser` | 3 | GET /all-status (×3), GET /stats/by-department (×2), GET /users (×1) |

> `AdminUser` 在 `on_start()` 時會快取 active event IDs，供所有 user class 共用。

### 驗收指標

| 指標 | 目標值 | 測量端點 |
|------|--------|---------|
| p95 回應時間 | < 500ms | POST /report |
| p95 回應時間 | < 200ms | GET /health |
| 錯誤率 | < 1% | 正常負載（38 users）|
| 吞吐量 | > 100 RPS | GET 類端點 |

HTML 報告位於 `tests/performance/reports/`（已加入 `.gitignore`）。

---

## 8. CI/CD Pipeline (GitHub Actions)

### 觸發條件

```yaml
on:
  push:
    branches: [main, "feature/**", "fix/**", "test/**", "docs/**"]
  pull_request:
    branches: [main]
```

- **Push 到任何 `feature/**` / `fix/**` / `test/**` / `docs/**` 分支**：開發中即時回饋（只跑測試 jobs，不觸發部署）
- **Push 到 `main`**：跑測試 jobs + `build-and-push`（推 image 到 Artifact Registry）+ `deploy`（GKE rolling update）
- **PR 到 `main`**：合併前完整驗證（僅測試 jobs）

### Pipeline 架構

```
Push / PR
    │
    ├──────────────────────────────────────────┐
    ▼                                          ▼
backend-unit                             frontend-unit
(no DB, ~1 min)                          (Vitest, ~1 min)
    │                                          │
    ▼                                          │
backend-integration ◄──────────────────────── ┘
(postgres service, ~3 min)
    │
    ▼
e2e
(docker compose + playwright, ~5-8 min)
```

| Job | 依賴 | 觸發條件 | 描述 |
|-----|------|---------|------|
| `backend-unit` | — | push / PR | 不需要 DB，先快速失敗 |
| `backend-integration` | — | push / PR | 使用 GitHub Actions service container 的 PostgreSQL |
| `frontend-unit` | — | push / PR | pnpm vitest run + coverage |
| `e2e` | `backend-integration` + `frontend-unit` | push / PR | 完整 stack 啟動後跑 Playwright |
| `build-and-push` | 上述 4 個全綠 | **只在 push 到 main** | 用 `GCP_SA_KEY` 認證、build + push backend/frontend image（`:<sha>` + `:latest`）到 Artifact Registry |
| `deploy` | `build-and-push` | **只在 push 到 main** | `kubectl set image` + `rollout status`（180s timeout），滾動部署到 GKE |

### Artifacts（測試產物）

每次 CI 執行後可下載：

| Artifact | 內容 |
|----------|------|
| `backend-coverage` | `coverage.xml`（供 SonarCloud 或 Codecov 使用）|
| `frontend-coverage` | `coverage/`（HTML 覆蓋率報告）|
| `playwright-report` | `playwright-report/`（截圖、影片、失敗紀錄）|

保存 14 天。

### 本機模擬 CI 流程

```bash
# 模擬 backend-unit
cd backend && pytest tests/unit/ -v --tb=short

# 模擬 backend-integration（需先啟動 db-test）
docker compose -f docker-compose.test.yml up db-test -d
export TEST_DATABASE_URL=postgresql+asyncpg://app:devpassword@localhost:5433/safety_response_test
pytest tests/integration/ -v --cov=app

# 模擬 frontend-unit
cd frontend && pnpm vitest run

# 模擬 e2e（需完整 stack）
docker compose up -d && sleep 10
cd tests/e2e && npx playwright test

# 一鍵執行全部後端測試（透過 Docker）
docker compose -f docker-compose.test.yml up --build --exit-code-from backend-test
```

---

## 9. 測試設計決策

### A. 為什麼用 Connection-level Transaction Rollback？

傳統隔離方式是每個測試結束後 `TRUNCATE ALL TABLES`，但這有兩個缺點：
1. 需要重新建立 schema（慢）
2. 外鍵約束的刪除順序很複雜

本系統使用 **connection-level transaction rollback**：

```python
connection = await test_engine.connect()
trans = await connection.begin()       # 開始 outer transaction
session = AsyncSession(bind=connection)  # session 綁定此 connection

yield session                           # 測試在 transaction 內執行

await session.close()
await trans.rollback()                  # 回滾所有操作
await connection.close()
```

優點：每個測試完成後 DB 完全恢復乾淨，速度快（不需要 DROP/CREATE）。

### B. 為什麼替換 App Lifespan？

`main.py` 的 `lifespan` 在啟動時呼叫 `seed_data()`，會建立 38 位使用者。若讓它在測試中執行：
- 38 位 seed users 會出現在測試 DB 中
- 計算 "所有 active users" 的測試就會失敗（3 位 test users vs. 41 位 seed+test users）

解決方式：在 `conftest.py` 中將 lifespan 替換為 no-op：

```python
@asynccontextmanager
async def _noop_lifespan(application):
    yield  # 不執行 create_all，不執行 seed_data

app.router.lifespan_context = _noop_lifespan
```

DB schema 改由 `test_engine` fixture 負責建立（`Base.metadata.create_all`）。

### C. 為什麼不 Mock 資料庫？

Integration tests 使用**真實 PostgreSQL**，原因：
- Mock DB 可能掩蓋真實的 SQL 錯誤（如 unique constraint、cascade delete）
- 本系統有複雜的業務邏輯（auto-generate reports、cascade delete）必須在真實 DB 環境驗證
- 使用 `asyncpg` 的非同步行為需要真實驅動程式才能正確測試

### D. 為什麼 E2E Tests 使用獨立 Browser Context？

每個角色（`adminPage`, `managerPage`, `employeePage`）都有獨立的 browser context（不同的 localStorage）。這確保：
- 測試可以平行執行
- 角色之間的 session 不會互相干擾
- 每個測試結束後 context 自動清理

### E. 為什麼性能測試不在 CI 中？

| 原因 | 說明 |
|------|------|
| 環境差異 | GitHub Actions runner 的 CPU/記憶體不穩定，會造成假陽性 |
| Seed data | 需要 38 位真實 seed users，CI test DB 是空的 |
| 執行時間 | 60-120 秒的測試太長，拖慢 PR feedback loop |
| 目的不同 | 性能測試是容量規劃工具，不是程式正確性驗證 |

---

## 10. 撰寫新測試指南

### 新增 Backend Integration Test

```python
# backend/tests/integration/test_my_feature.py
import pytest

@pytest.mark.integration
class TestMyFeature:
    async def test_happy_path(self, client, admin_headers, active_event):
        r = await client.post(
            f"/api/events/{active_event.id}/some-endpoint",
            json={"key": "value"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["field"] == "expected"

    async def test_unauthorized(self, client, employee_headers, active_event):
        r = await client.post(
            f"/api/events/{active_event.id}/some-endpoint",
            json={"key": "value"},
            headers=employee_headers,
        )
        assert r.status_code == 403
```

**可用 fixtures**：`client`, `db_session`, `admin_user`, `manager_user`, `employee_user`, `admin_headers`, `manager_headers`, `employee_headers`, `active_event`

若需要**額外的測試使用者**，在測試函式或模組的 conftest 中新增 fixture：

```python
@pytest_asyncio.fixture()
async def second_employee(db_session, manager_user):
    user = User(
        employee_id="TEST_E002",
        name="Second Employee",
        email="e2@example.com",
        password_hash=hash_password("testpassword"),
        role="employee",
        manager_id=manager_user.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user
```

### 新增 Frontend Unit Test

```typescript
// frontend/src/__tests__/components/MyComponent.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import MyComponent from '../../components/MyComponent'

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent prop="value" />)
    expect(screen.getByText('Expected Text')).toBeInTheDocument()
  })

  it('handles user interaction', async () => {
    const handler = vi.fn()
    render(<MyComponent onAction={handler} />)
    await userEvent.click(screen.getByRole('button', { name: 'Click Me' }))
    expect(handler).toHaveBeenCalledOnce()
  })
})
```

### 新增 Playwright E2E Test

```typescript
// tests/e2e/specs/my-feature.spec.ts
import { test, expect } from '../fixtures/auth.fixture'

test.describe('My Feature', () => {
  // 使用已登入的 adminPage / managerPage / employeePage
  test('admin can use my feature', async ({ adminPage: page }) => {
    await page.goto('/admin/my-feature')
    await expect(page.getByRole('heading')).toBeVisible()

    await page.getByRole('button', { name: 'Do Something' }).click()
    await expect(page.getByText('Success')).toBeVisible()
  })

  // 不需要登入的測試，直接用 page
  test('unauthenticated redirect', async ({ page }) => {
    await page.goto('/admin/my-feature')
    await expect(page).toHaveURL(/\/login/)
  })
})
```

---

## 11. 常見問題 (FAQ)

### Q1: Integration tests 報錯 `asyncpg.InvalidCatalogNameError`

資料庫不存在，請先建立：

```bash
# 本機 PostgreSQL
createdb -U app safety_response_test

# 或用 Docker
docker compose -f docker-compose.test.yml up db-test -d
```

### Q2: `asyncio_default_fixture_loop_scope` 警告訊息

已在 `pytest.ini` 中設定 `asyncio_default_fixture_loop_scope = session`，若仍出現可加入：

```ini
filterwarnings =
    ignore::DeprecationWarning
```

### Q3: Frontend tests 報錯 `Cannot find module 'jsdom'`

```bash
cd frontend && pnpm add -D "jsdom@^24.0.0"
```

> 注意：jsdom 29+ 與 Node 18 不相容，請使用 24.x 版本。

### Q4: E2E tests 連不到 `http://localhost:5173`

確認 Docker stack 已完整啟動：

```bash
docker compose ps
# 確認 frontend 和 backend 都是 running

# 測試連線
curl http://localhost:5173
curl http://localhost:8000/health
```

### Q5: Playwright 測試失敗，但本機手動操作正常

查看截圖與 trace：

```bash
cd tests/e2e
npx playwright test --reporter=html
npx playwright show-report playwright-report

# 顯示 trace（更詳細的操作紀錄）
npx playwright show-trace test-results/<test-name>/trace.zip
```

### Q6: 如何只執行快速測試（不含 DB）？

```bash
# 只跑不需要 DB 的測試
pytest tests/unit/ -v -m "not integration"

# 前端不需要 DB
cd frontend && pnpm vitest run
```

### Q7: Coverage 報告在哪裡？

| 類型 | 位置 |
|------|------|
| 後端 HTML 覆蓋率 | `backend/htmlcov/index.html` |
| 後端 XML（for CI） | `backend/coverage.xml` |
| 前端 HTML 覆蓋率 | `frontend/coverage/index.html` |
| Playwright 報告 | `tests/e2e/playwright-report/index.html` |
| Locust 報告 | `tests/performance/reports/*.html` |

---

*文件最後更新：2026-05-25*  
*對應 git branch：`main`*

### 更新歷程

| 日期 | 變更 |
|------|------|
| 2026-05-10 | 初版（feature/testing 分支）|
| 2026-05-25 | 新增 7 個前端測試檔（FacilitySelector、Navbar、Login、ReportPage、events/users/reports API client，約 +55 test cases）；CI push trigger 補上 `test/**` 與 `docs/**`；CI/CD pipeline 表格補上 `build-and-push` / `deploy` 兩個 main-only job |
