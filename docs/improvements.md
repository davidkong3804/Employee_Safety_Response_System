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
| A1 | `docs/architecture.md` L52-54 | 寫 backend HPA「3–30 pods」、frontend「2–10 pods」 | 實際 `minReplicas: 1`（`k8s/07-backend-hpa.yaml`、`k8s/09-frontend-hpa.yaml`） |
| A2 | `docs/deployment.md` L119-120 | 同上，寫「Backend HPA: 3–30」「Frontend HPA: 2–10」 | 同上，應為 1–30 / 1–10 |
| A3 | `docs/deployment.md` L139-144 | 寫 `max_connections=200`、`30 x 5 = 150 < 200` | 實際 `k8s/03-postgres.yaml` 設 `max_connections=350` |
| A4 | `k8s/01-configmap.yaml` L17-19 | 註解寫 `60 x (3+2) = 300 < 350` | backend HPA `maxReplicas` 實際是 30，不是 60 |
| A5 | `docs/er-diagram.md` EVENTS 表 L22-32 | 缺 `facility` 欄位 | `Event.facility` 已改為 `ARRAY(String(50))`（多選廠區），ER 圖需補上 `varchar(50)[] facility` |
| A6 | `docs/api-spec.md` `POST /api/events` 請求範例 L72-80 | 請求 body 缺 `facility` 欄位 | `EventCreate` 已支援 `facility: list[str] \| null`（多選廠區，省略=全廠區） |

> 註：`er-diagram.md` L15 與 `api-spec.md` L53 的 `facility` 是 **User** 的欄位，仍為 `varchar(50)` 字串，**正確不需改**。只有 **Event** 的 facility 改成了陣列。

**建議**：統一以 manifests / 程式碼為準，把上述六處文件 / 註解改成
backend 1–30、frontend 1–10、`max_connections=350`、`30 x 5 = 150 < 350`，
並在 ER 圖與 API spec 補上 Event 的多選 `facility` 欄位。

---

## B. 前端可優化 🟡

| # | 位置 | 問題 | 建議 |
|---|------|------|------|
| B1 | `EventManagement.tsx` `handleClose` / `handleDelete` | 無 `try/catch`，API 失敗時不會顯示錯誤 toast，使用者以為成功 | 比照 `handleCreate` 加上 `try/catch` + `toast.error` |
| B2 | `UserManagement.tsx` `handleDeactivate` | 同上，無錯誤處理 | 同上 |
| B3 | `EventManagement.tsx` 刪除事件 / `UserManagement.tsx` 停用使用者 | 點下去**立即執行**，無二次確認 | 加 confirm dialog（破壞性操作） |
| B4 | 各 Create / 送出按鈕 | 送出期間未 disable，連點可能重複建立 | submit 期間 `disabled` + loading 狀態 |
| B5 | `Login.tsx` L74-77 | 登入頁直接印出 demo 帳密（A001 / M001 / E001） | 正式環境應移除，或用 `import.meta.env.DEV` 包起來只在開發顯示 |

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
| E1 | GitHub repo Settings | 🔴 | `GCP_SA_KEY` / `GKE_CLUSTER` / `GKE_REGION` 三個 secret 尚未設定，build/deploy job 會失敗 | 一次性設定（值：cluster `safety-response`、zone `asia-east1-a`，SA 需 `artifactregistry.writer` + `container.developer`） |
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

---

## 建議處理順序

1. **🔴 E1** — 設定 CI secrets，讓 pipeline 能跑（GitHub UI 操作，僅你能做）
2. ~~🔴 D1~~ — ✅ secrets 已移出版控；正式上線前仍須換真值並評估 Secret Manager
3. **🟡 A1–A6** — 修文件不一致（低成本、避免誤導）
4. **🟡 B1–B4** — 前端錯誤處理與二次確認（體驗品質）
5. **🟡 E2** — 導入 Kustomize 解決 image tag drift
6. **🟡 C3** — Redis 接上 dashboard 快取（壓測前做，效益明顯）
7. **🟢 F、G** — 監控與未來功能，依專案時程排入
