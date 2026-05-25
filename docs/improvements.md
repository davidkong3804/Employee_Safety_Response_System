# 待辦與優化清單 (Improvements Backlog)

> 本文件整理 Employee Safety & Response System 目前**尚未完成**或**可優化**的項目，
> 供後續調整參考。更新日期：2026-05-21。
>
> 優先級：🔴 P0 上線阻礙 / 安全 · 🟡 P1 維運與體驗品質 · 🟢 P2 加分項與未來功能

---

## A. 文件與程式碼不一致 🟡

這幾處是**舊文件沒跟上 manifests**，會誤導後續維運者。修正成本低。

| # | 位置 | 問題 | 正確值 |
|---|------|------|--------|
| A1 | ~~`docs/architecture.md` L52-54 + L174~~ | ✅ **已修 (2026-05-25)**：圖內副本數改為 1–30 / 1–10；scalability section 一併改 | — |
| A2 | ~~`docs/deployment.md` L119-120~~ | ✅ **已修 (2026-05-25)**：改為「Backend HPA: 1–30」「Frontend HPA: 1–10」 | — |
| A3 | ~~`docs/deployment.md` L139-144~~ | ✅ **已修 (2026-05-25)**：算式改為 `30 x 5 = 150 < 350`，敘述更新成 `max_connections=350` + 60 pods 為 pgbouncer 上限門檻 | — |
| A4 | ~~`k8s/01-configmap.yaml` L17-19~~ | ✅ **已修 (2026-05-25)**：註解改寫成 `30 x (3+2) = 150 < 350`，並說明 60 pods 是擴充上限（要 pgbouncer 就上）| — |
| A5 | ~~`docs/er-diagram.md` EVENTS 表~~ | ✅ **已修 (2026-05-25)**：EVENTS 表加上 `facility` 陣列欄位 + Table Details 補上 facility 章節說明 | — |
| A6 | ~~`docs/api-spec.md` `POST /api/events`~~ | ✅ **已修 (2026-05-25)**：POST 範例 body 含 `facility` 陣列、補上 `facility` 欄位的語意說明（空/null = 全廠區）| — |

> 註：`er-diagram.md` L15 與 `api-spec.md` L53 的 `facility` 是 **User** 的欄位，仍為 `varchar(50)` 字串，**正確不需改**。只有 **Event** 的 facility 改成了陣列。

**建議**：統一以 manifests / 程式碼為準，把上述六處文件 / 註解改成
backend 1–30、frontend 1–10、`max_connections=350`、`30 x 5 = 150 < 350`，
並在 ER 圖與 API spec 補上 Event 的多選 `facility` 欄位。

---

## B. 前端可優化 🟡

| # | 位置 | 問題 | 建議 |
|---|------|------|------|
| B1 | ~~`EventManagement.tsx`~~ | ✅ **已修 (2026-05-25)**：`handleClose` / `handleDelete` 補 `try/catch` + 失敗 toast | — |
| B2 | ~~`UserManagement.tsx`~~ | ✅ **已修 (2026-05-25)**：`handleDeactivate` 補 `try/catch` + 失敗 toast | — |
| B3 | ~~破壞性操作~~ | ✅ **已修 (2026-05-25)**：關閉事件 / 刪除事件 / 停用使用者三處皆加 `window.confirm` 二次確認，i18n 文案分開（close/delete/deactivateConfirm）| — |
| B4 | ~~各 Create 按鈕~~ | ✅ **已修 (2026-05-25)**：EventManagement / UserManagement 加 `submitting` state，送出期間 `disabled` + 顯示 "Creating..." 文案 | — |
| B5 | ~~`Login.tsx`~~ | ✅ **已修 (2026-05-25)**：demo 帳密 div 用 `import.meta.env.DEV` 包起來，正式 build 不會打包 | — |

---

## C. 後端可優化 🟡

| # | 位置 | 問題 | 建議 |
|---|------|------|------|
| C1 | `events/router.py` `create_event` L80-82 | 逐筆 `db.add(report)` 迴圈建立 placeholder | 員工數上萬時應改 `insert().values([...])` 批次插入 |
| C2 | `events/router.py` `update_event` L106 | 用 full `db.refresh(event)`，與 `create_event` 的 targeted refresh（`attribute_names=['created_at']`）不一致 | **需驗證**：若 asyncpg 讀回 `ARRAY` 欄位的問題仍在，編輯有廠區的事件會踩雷。建議統一改 targeted refresh |
| C3 | `reports/router.py` `get_event_stats` / `stats/by-department` | 每次 30 秒輪詢都打未快取的彙總查詢，多位 manager 同時看會放大 DB 負載 | 用已部署的 Redis 做短 TTL 快取（5–10 秒）；參見 `docs/deployment.md` Known limitations |
| C4 | `list_events` / `list_users` / `all-status` / `team-status` | 無分頁，一次回傳全部 | 大規模部署加 `limit`/`offset` 或 cursor 分頁 |
| C5 | 全專案 | 無 DB migration 機制，schema 改動需重建表（Alembic 已安裝未用） | schema 要對 live data 演進時導入 Alembic |

---

## D. Kubernetes / 部署 🔴🟡

| # | 位置 | 優先 | 問題 | 建議 |
|---|------|------|------|------|
| D1 | `k8s/02-secret.yaml` | 🟡 | ✅ **已修**：`02-secret.yaml` 移出版控（改 `02-secret.yaml.example` 範本 + 加入 `.gitignore`），真實 secret 不再進 git。**仍待辦**：① 把線上叢集的 `JWT_SECRET` 用 `openssl rand -hex 32` 換成真值；② 正式環境評估改用 GCP Secret Manager + Secrets Store CSI driver | 詳見 H 區與 `docs/deployment.md` 步驟 2 |
| D2 | `k8s/10-ingress.yaml` | 🟡 | 尚未加 `kubernetes.io/ingress.allow-http: "false"` | Google-managed cert 變 ACTIVE 後手動補上，強制 HTTPS |
| D3 | `k8s/03-postgres.yaml` | 🟡 | 單實例 Postgres，無 HA、無自動備份 | 正式環境改用 Cloud SQL for PostgreSQL |
| D4 | `k8s/04-redis.yaml` | 🟢 | Redis 已部署但程式碼沒用到 | 接上 C3 的 dashboard 快取後才有意義 |
| D5 | `k8s/05-db-init-job.yaml` | 🟢 | image 寫死 `:v1`；Job spec 不可變 | 換 backend image / 改 schema 後，需手動 `kubectl delete job db-init && kubectl apply` |

---

## E. CI/CD 🔴

| # | 位置 | 優先 | 問題 | 建議 |
|---|------|------|------|------|
| E1 | ~~GitHub repo Settings~~ | 🟢 | ✅ **已完成 (2026-05-25)**：使用者已在 GitHub Settings → Actions secrets 設定 `GCP_SA_KEY` / `GKE_CLUSTER` / `GKE_REGION`，CI 後續 push 到 main 會自動跑 build-and-push + deploy | — |
| E2 | `k8s/06-backend.yaml`、`08-frontend.yaml` | 🟡 | manifests image 寫死 `:v1`，但 deploy job 用 `kubectl set image` 設成 `:<git-sha>` → 兩者 drift。任何人跑 `kubectl apply -f k8s/` 會把線上 image revert 回 `:v1` | 導入 Kustomize，用 `images:` override 由 CI 動態帶 tag；或 deploy 後讓 CI 回寫 manifests |

---

## F. 監控與可觀測性 🟢

來源：`docs/handoff.md`（已規劃為交接任務，尚未實作）。

| # | 項目 | 說明 |
|---|------|------|
| F1 | FastAPI metrics export | `backend/requirements.txt` 加 `prometheus-fastapi-instrumentator`，`main.py` 加 1 行 middleware 暴露 `/metrics` |
| F2 | Managed Prometheus 抓取 | `k8s/06-backend.yaml` pod template 加 `prometheus.io/*` annotation（或改用 `PodMonitoring` CRD） |
| F3 | Cloud Monitoring alerts | HPA 觸頂、Pod 頻繁重啟、API p95 > 1s、DB 連線數過高 → email 通知 |
| F4 | 壓力測試報告 | `tests/performance/locustfile.py` 已備好，需跑三階段（50/200/500 users）並產出 `docs/stress-test-report.md` |

---

## G. 功能性未完成（規格內標註的 future enhancements）🟢

來源：`docs/user-stories.md` 中標 `[ ]` 的驗收條件。皆為**規格認可的未來功能**，非缺陷。

| User Story | 未完成項目 |
|-----------|-----------|
| US-1 一鍵回報 | 離線模式（本地快取 + 自動重送） |
| US-2 醫療求助 | 防誤觸（長按 / 雙重確認）、Wi-Fi AP 定位、誤觸取消 |
| US-4 即時儀表板 | 高負載 graceful degradation |
| US-5 自動催報 | 可設定時間門檻（15/30/60 分）、多管道通知（SMS / 語音）、自動排除傷者 |
| US-6 跨廠區篩選 | 依組織階層的權限控制、離線廠區標示 |
| US-9 系統分析 | 回應時間 metrics、提醒成效分析 |

---

## H. 已完成（本輪及先前）✅

供對照，以下項目**已處理完畢**，不需再動：

- 後端 18 個 API endpoints、RBAC、soft delete、event cascade delete
- 多選廠區（TSMC 國家→地區→廠區階層）、`Event.facility` 改 `ARRAY` 型別
- 前端 i18n 補完（含 `common.status`、`event.facility`、`user.roles.*`、`dashboard.refresh`）
- 登入後依角色分流（admin→`/admin/events`、manager→`/dashboard`、employee→`/`）
- 各頁 table header 加 `whitespace-nowrap`
- k8s CORS 改為實際網域 `employee-safety.duckdns.org`
- CI/CD pipeline（build + push + deploy 到 GKE，僅 main 觸發）
- `k8s/11-network-policy.yaml`（default-deny + allow-list，DB/Redis 不可被 frontend 直連）
- 測試：後端 unit/integration、前端 Vitest、E2E Playwright、Locust 皆完整
- 遠端分支清理（feature/testing、docs/handoff 已合併或刪除）
- **D1（部分）**：`k8s/02-secret.yaml` 移出版控 — 改 `02-secret.yaml.example` 範本 + `.gitignore`，`docs/deployment.md`、`CLAUDE.md` 同步更新部署步驟
- **前端測試覆蓋擴充（2026-05-25）**：補上 7 個 Vitest 測試檔，約 55 個 test cases，CI 全綠
  - API client：`events.test.ts`、`users.test.ts`、`reports.test.ts`
  - 元件：`FacilitySelector.test.tsx`（全廠區 toggle、國家展開、disabled 邏輯）、`Navbar.test.tsx`（角色 nav + 登出）
  - 頁面：`Login.test.tsx`（登入後依角色 redirect）、`ReportPage.test.tsx`（一鍵回報核心流程 / 已回報視圖）
  - 同步擴充 `vitest.setup.ts` 的 i18n keys（`app.title` / `report.*` / `event.allFacilities` / `facility.*`）
- **CI trigger 補洞（2026-05-25）**：`.github/workflows/ci.yml` 的 `push.branches` 原本只列 `[main, feature/**, fix/**]`，`test/**` 與 `docs/**` 分支推送會靜默不跑 CI（上面前端測試擴充 PR 第一次推就踩到）。補上後所有慣用 prefix 都會跑測試 jobs；`build-and-push` 與 `deploy` 仍 gate 在 main，不會誤觸發部署
- **程式碼品質基線（2026-05-25）**：先前評鑑時發現是唯一硬缺口，現補上
  - 前端：`frontend/eslint.config.js`（ESLint 9 flat config，TypeScript + 瀏覽器/測試 globals，rules 採寬鬆策略避免動到既有 code）+ `.prettierrc.json`（吻合既有 no-semi / single-quote 風格）+ `.prettierignore`
  - 後端：`backend/pyproject.toml` 加上 `[tool.ruff]` 設定（F + E + W + I 規則 + isort，line-length=120，tests 目錄放寬 F401/F811）
  - CI：新增 `lint` job（Job 0），跑 `ruff check` + ESLint，Prettier `--check` 標 `continue-on-error` 為轉移期（codebase 預先存在不符 Prettier 格式的檔案）
  - 工具不寫進 `package.json` / `requirements.txt`，CI 用 `npm install -g` / `pip install` 動態安裝，避免 lockfile 同步問題
  - **A5/A6 同步修畢**：ER 圖 + API spec 補上 Event.facility 陣列說明
- **文件不一致修補（2026-05-25）**：A5、A6 完成（見 A 區）
- **文件 + UX 清理一輪（2026-05-25 第二批）**：
  - 🟡 **A1–A4** 全清：架構圖 / deployment.md / configmap 註解中的 HPA 副本數與 `max_connections` 一致改為 1–30 / 1–10 / 350，算式同步成 `30 x 5 = 150 < 350`
  - 🟡 **B1–B5** 全清：
    - EventManagement `handleClose` / `handleDelete`、UserManagement `handleDeactivate` 補完 try/catch + 失敗 toast
    - 破壞性操作（關閉事件 / 刪除事件 / 停用使用者）加上 `window.confirm` 二次確認，i18n 文案分開（`event.closeConfirm` / `event.deleteConfirm` / `user.deactivateConfirm`）
    - 送出按鈕 `disabled` + "Creating..." 顯示，避免連點重複建立
    - Login 頁 demo 帳密 div 用 `import.meta.env.DEV` 包起來，production build 不會打包
  - 🔴 → 🟢 **E1**：使用者完成 GitHub Secrets 設定（`GCP_SA_KEY` / `GKE_CLUSTER` / `GKE_REGION`），CI/CD pipeline 從此全啟用
- **GKE login load-test 三連修 + 容量上修（2026-05-25 第三批）**：診斷 Locust 對 GKE 跑壓測時登入大量失敗，三個根因一次解決，並把容量目標從 1000 拉到 15000
  - **(1) 資料不存在 + idempotency bug**：cluster 的 db-init Job 是早期 seed（只有 E001–E030）後跑的，後來 seed.py 擴 → 1000 → 15000 員工，但 `seed_data()` 用「有任何 user 就 return」做 idempotency，重跑無效。改為：
    - 先撈現有 employee_ids snapshot，逐筆 skip 已存在、新建缺少的
    - 把員工數量改成常數 `LOAD_TEST_MAX_EMPLOYEES = 15000`（seed.py + locustfile.py 同步），未來改一處就好
    - 對於既有 active event，自動為新增 users 補 placeholder report（filter facility + is_active，鏡像 production `POST /api/events` 邏輯），這樣 Locust 的 `submit_report` 不會 404
    - 全新 DB 場景照舊建 2 個 demo events 與全部 placeholder reports
  - **(2) event loop 被 bcrypt 卡住**：`verify_password` 是同步 bcrypt（~250ms/次）在 async login 路由內呼叫，**鎖住整個 asyncio event loop**，單 pod 登入上限 ~4 req/s。改用 `asyncio.to_thread(bcrypt.checkpw, ...)` 把 CPU 工作丟去 thread pool；`test_auth_utils.py` 三個 verify 測試一併改 async
  - **(3) Job 再執行不拿新映像**：`k8s/05-db-init-job.yaml` image tag 寫死 `:v1`，即使重 build 後 `kubectl delete job && apply` 還是跑舊版 seed。改成 `:latest` + `imagePullPolicy: Always`，每次重跑都會拉最新 build
  - 配套：使用者需在 main merge 完、CI 把新 backend image 推到 Artifact Registry 後，跑 `kubectl -n safety-system delete job db-init && kubectl apply -f k8s/05-db-init-job.yaml`，新 seed 會補上 E0031–E15000（約 30 秒）並為既有 active event 自動 top-up placeholders

---

## 建議處理順序

1. ~~🔴 E1~~ — ✅ secrets 已設定，CI/CD pipeline 全啟用
2. ~~🔴 D1~~ — ✅ secrets 已移出版控；正式上線前仍須換真值並評估 Secret Manager
3. ~~🟡 A1–A6~~ — ✅ 全清
4. ~~🟡 B1–B5~~ — ✅ 全清
5. **🟡 E2** — 導入 Kustomize 解決 image tag drift
6. **🟡 C3** — Redis 接上 dashboard 快取（壓測前做，效益明顯）
7. **🟡 Prettier strict 化** — 跑一次 `pnpm exec prettier --write src/`，然後拿掉 CI 的 `continue-on-error`
8. **🟡 C1 / C2 / C4 / C5** — 後端優化（bulk insert、targeted refresh 一致化、分頁、Alembic）
9. **🟡 D2–D5** — k8s 部署面（HTTPS 強制、Cloud SQL HA、db-init Job 重跑流程）
10. **🟢 F、G** — 監控與未來功能（F1/F2 已由隊友建好 Prometheus + Grafana + alerts），依專案時程排入
