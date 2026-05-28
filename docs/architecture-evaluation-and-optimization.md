# 🏆 企業營運緊急應變回報系統：架構評估與雲原生優化報告
> **NTU Cloud Native Course Final Project Evaluation & Observability Masterpiece**

本文件根據台積電（TSMC）評審與台灣大學期末報告規範，對**企業營運緊急事件安全回報系統**（Employee Safety & Response System）進行全方位的架構評估與深度優化設計。本文件旨在對齊專案期末評分項度（需求轉換 30%、架構設計 25%、系統測試 25%、程式碼品質 10%、運維與可靠性 10%），並提出未來大型架構調整與優化建議。

---

## 🗺️ 專案期末報告評分項度對齊目錄
1. [需求轉換與實作 (30%)](#1-需求轉換與實作-30)
2. [架構設計與可擴展性 (25%)](#2-架構設計與可擴展性-25)
3. [系統測試與驗證 (25%)](#3-系統測試與驗證-25)
4. [程式碼品質與安全性 (10%)](#4-程式碼品質與安全性-10)
5. [運維、可觀測性與可靠性 (10%)](#5-運維可觀測性與可靠性-10)
6. [全面架構調整與未來深海優化建議](#6-全面架構調整與未來深海優化建議)

---

## 1. 需求轉換與實作 (30%)

我們將企業「緊急事件回報」與「主管關懷統計」需求，轉譯為符合敏捷開發的 **User Stories** 與 **Acceptance Criteria (AC)**，並成功實作：

*   **US-1 一鍵快速回報（員工端）**
    *   *需求*：員工在大地震等天災發生時，需在 3 秒內完成「安全」或「需要協助」回報，避免繁雜填表。
    *   *實作*：前端提供大尺寸語系化按鈕，後端提供 `POST /api/events/{id}/report` 接口，並透過 Redis Write Buffer 緩衝寫入，承載數萬人瞬時併發。
*   **US-2 主管統計報表與催報（主管端）**
    *   *需求*：各廠區主管需即時掌握轄下部門的回報狀態（已回報/未回報/需要協助名單），並對未回報員工進行催報。
    *   *實作*：後端實作 `GET /api/events/{id}/stats/by-department` 統計接口，結合 Composite Index 與 Redis 記憶體快取。主管可一鍵觸發 `POST /api/events/{id}/remind` 發送通知。
*   **US-3 事件發布與組織控管（管理員端）**
    *   *需求*：管理員發布事件時可限定廠區（如僅限竹科 Fab12B），並自動為受影響員工建立空回報記錄（Placeholders）。
    *   *實作*：發布事件時使用 PostgreSQL Core 批量寫入技術（`executemany`），在 1-2 秒內為 **15,000+** 位受影響員工秒速生成回報佔位行，提供完美的預熱資料庫狀態。
*   **組織架構變更防禦 (C6 Org-Snapshot)**
    *   *實作*：在發布事件時，將員工當時的 `manager_id`、`department` 與 `facility` 快照（Snapshot）寫入 `safety_reports` 表中，防範未來組織架構調整（如員工換部門）導致歷史事件報表失真。

---

## 2. 架構設計與可擴展性 (25%)

我們的系統採用業界標準的**雲原生微服務架構**，具備優異的水平擴展性（Scalability）：

### 2.1 高併發架構與 Redis 寫入緩衝 (Write Buffer)
在天災發生後，數萬名員工會同時湧入回報，若直連資料庫進行 `UPDATE` 會瞬間鎖定資料表並耗盡 DB 連線池。

```
[ 15,000+ Employees ] ──( 瞬間高併發 )──> [ FastAPI Pods ]
                                                │
                                    (O(1) Atomic Pipeline)
                                                ▼
                                        [ Redis Buffer ]
                                                │
                                        (每 2 秒非同步 Batch)
                                                ▼
                                       [ PostgreSQL DB ]
```

1.  **Redis 滑動窗口速率限制器 (Rate Limiter)**：使用 Redis ZSET 原子指令（`ZADD`, `ZREM`, `ZCARD`）實作，限制同一員工在 10 秒內僅能請求 5 次，防範前端 retry 風暴與惡意連點。
2.  **寫入快取緩衝 (Redis Write Buffer)**：員工提交回報時，FastAPI Pod 會優先將資料寫入 Redis 記憶體 Buffer（O(1)），隨即直接返回成功響應。後端背景執行程（`app/background.py`）每 2 秒將 Buffer 內的回報以 **Batch Update** 批量沖刷（Flush）至 PostgreSQL，大幅減輕 DB 負載。

### 2.2 關聯資料模型與複合索引 (ER Model & Indexing)
為了解決主管查詢報表時的資料庫全表掃描（Full Table Scan）痛點，我們針對核心關聯欄位進行了索引優化：

```sql
-- 催報關聯唯一複合索引 (防止重複催報與慢查詢)
CREATE UNIQUE INDEX idx_reminders_event_user ON reminders (event_id, user_id);

-- 安全報告查詢複合索引 (加速主管 Dashboard 查詢)
CREATE INDEX idx_reports_event_user_status ON safety_reports (event_id, user_id, status);
```

*   **關係載入解除 (selectin Loading Trap 解除)**：我們將 `User` 模型中主管與屬下關係從遞迴的 `selectin` 改為 `lazy="select"`，解除高負載下資料庫查詢因遞迴載入而產生的 OOM 記憶體炸彈。

---

## 3. 系統測試與驗證 (25%)

為了通過評審對系統品質與穩定性的嚴格審查，我們建立了高覆蓋率的測試驗證體系：

### 3.1 單元測試與 TypeScript 編譯
*   **後端單元測試**：使用 `pytest` 覆蓋 38 項核心邏輯，包含滑動窗口速率限制、密碼 Argon2 雜湊、JWT 權限校驗、電話格式化以及資料 Schema 驗證。
    *   *執行結果*：`38 passed in 1.80s` (100% 綠色通過)。
*   **前端靜態檢查**：在 CI/CD 中加入 TypeScript 嚴格靜態型別編譯檢測，防止任何 runtime undefined 錯誤。
    *   *執行結果*：`npx tsc --noEmit` (100% 綠色通過)。

### 3.2 15,000 人規模大型壓力測試 (Locust)
*   **測試設計**：壓測腳本位於 `tests/performance/locustfile.py`，模擬 15,000 位高擬真員工的真實行為。
*   **預熱機制**：測試資料庫已預熱 15,000 位真實員工資料，Locust 執行時可均勻抽選隨機憑證進行高併發 `POST` 回報，確保壓測真實性。
*   **防禦驗證**：在持續加壓下，HPA 自動將 FastAPI Pods 從 3 擴容至 30 個，並驗證 Redis 滑動窗口正確拋出 `HTTP 429 Too Many Requests`，成功保護 DB 連線池不崩潰。

---

## 4. 程式碼品質與安全性 (10%)

安全性與代碼維護性是專案評分的重點。我們針對系統進行了深度的漏洞修復與防禦性重構：

1.  **Redis 使用者快取去密碼化 (Remove Cached `password_hash`)**
    *   *安全性漏洞*：原先 Redis 中會連帶緩存使用者的 `password_hash`，有快取滲透外洩的風險。
    *   *防禦修復*：完全將密碼雜湊移出快取。當從快取反序列化 User 物件時，將其還原為空字串 `""`。真正的登入校驗流程直連 DB 查詢，確保快取資料無密碼殘留。
2.  **SQL 模糊搜尋萬用字元注入防護 (ILike Wildcard Escaping)**
    *   *安全漏洞*：在管理員搜尋員工時，若使用者輸入 `%` 或 `_`，會觸發 SQL 通配符查詢，在大資料量下會造成嚴重的 SQL 全表掃描並佔滿 CPU。
    *   *防禦修復*：在搜尋關鍵字中，使用 `escaped_search = search.replace("/", "//").replace("%", "/%").replace("_", "/_")` 進行轉義，並在 SQLAlchemy 查詢中加上 `escape="/"`。
3.  **嚴格輸入 Schema 校驗 (Pydantic Literal Enums)**
    *   *防禦修復*：在 API 接收端為所有狀態、嚴重度、角色欄位加入 `Literal` 校驗（如 `status: Literal["safe", "need_help"]`），在 Controller 層即時阻斷非法列舉字串，避免傳入 DB 產生 500 Server Error。
4.  **前端錯誤邊界與容錯 (Custom React ErrorBoundary)**
    *   *UI 品質*：新增全局 React `ErrorBoundary` 元件，當單一元件崩潰時，會優雅地渲染「網頁發生錯誤」並提供「重新載入」按鈕，徹底告別瀏覽器難看的死白畫面，提升應用韌性。

---

## 5. 運維、可觀測性與可靠性 (10%)

為了對齊期末簡報中**運維監控與可靠性（10%）**的硬性指標，我們為 GKE 部署了完整、立體化的自建 Prometheus + Grafana 監控體系，涵蓋四大範疇：

```
                    📊 Grafana 視覺化儀表板
                              │
                    🔥 Prometheus 採集器
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
[ 應用業務指標 ]        [ 基礎架構指標 ]        [ 資料庫/快取指標 ]
- 廠區回報速率          - Pod CPU/Memory        - DB 活躍連線數
- 活躍事件統計          - HPA 擴容動態          - DB 交易吞吐量
- Redis 命中比率        - Container 重啟次數     - Redis 記憶體使用率
```

### 5.1 Prometheus 與 Grafana 立體化監控設計
我們新建並調整了 5 個 K8s 部署檔案（`14-prometheus.yaml`, `15-grafana.yaml`, `17-postgres-exporter.yaml`, `18-redis-exporter.yaml`, `19-kube-state-metrics.yaml`），在叢集內實現了以下四個維度的即時監控：

#### 🟩 維度 A：基礎 HTTP 效能監控
*   **採集指標**：`http_requests_total`, `http_request_duration_seconds_bucket`
*   **視覺化面板**：Request Per Second (RPS)、4xx/5xx 錯誤率圖表、p50/p90/p95/p99 響應時間時延圖、以及各 Pod 負載分配。

#### 🟦 維度 B：自訂核心業務監控 (Business KPIs)
*   **採集指標**：
    *   `safety_reports_submitted_total{status, facility}` (Counter)：安全報告回報速率（按狀態、所屬廠區分類）。
    *   `safety_active_events_count{severity}` (Gauge)：當前進行中的緊急事件數量（按嚴重等級分類）。
    *   `safety_cache_operations_total{op="hit|miss"}` (Counter)：Redis 快取命中與失效比率。
*   **視覺化面板**：實時回報曲線（按廠區分流）、活躍事件水位線、快取分流命中率圓餅圖。

#### 🟨 維度 C：資料庫與快取健康度監控 (Exporters)
*   **採集指標**：
    *   `pg_stat_database_numbackends` (Gauge)：PostgreSQL 實時活躍連線數。
    *   `pg_stat_database_xact_commit` / `pg_stat_database_xact_rollback` (Counter)：DB 事務提交與回滾速率。
    *   `redis_memory_used_bytes` (Gauge)：Redis 記憶體實質佔用。
    *   `redis_commands_processed_total` (Counter)：Redis 吞吐量 (Ops/sec)。
*   **視覺化面板**：DB 連線水位面板（防止連線池枯竭）、Postgres 交易率圖、Redis 記憶體警告線、Redis Ops/sec 曲線。

#### 🟧 維度 D：Kubernetes 叢集與 Pod 資源監控 (Pod Resource Observability)
*   **採集指標**（透過部署 `kube-state-metrics`）：
    *   `kube_horizontalpodautoscaler_status_current_replicas` (Gauge)：HPA 當前副本數。
    *   `kube_pod_container_status_restarts_total` (Counter)：Pod 異常重啟次數。
*   **視覺化面板**：HPA Replicas 擴容歷史圖（清晰捕捉 3 -> 30 Pods 軌跡）、Pod 異常重啟監控器。

### 5.2 自動告警規則與自癒機制
定義於 `k8s/14-prometheus.yaml` 中，能夠在高負載壓測或生產環境故障時即時觸發警告：
*   **`BackendDown` (Critical)**：當後端 pod 無法被 scrape 超過 1 分鐘時觸發。
*   **`HighErrorRate` (Critical)**：當 HTTP 5xx 錯誤率超過 5% 持續 1 分鐘時觸發。
*   **`HighLatency` (Warning)**：當 API 的 p95 回應時間大於 1 秒持續 2 分鐘時觸發。
*   **`High4xxRate` (Warning)**：當 HTTP 4xx 超過 20% 持續 2 分鐘時觸發（警示潛在的惡意攻擊或大量 Rate Limiting）。
*   **`BackendPodRestarting` (Warning)**：當後端 Pod 在 5 分鐘內重啟超過 2 次時觸發（警示 OOMKilled 或崩潰）。

---

## 6. 全面架構調整與未來深海優化建議

本系統在**資料庫與快取層已完成了高規格的雲原生託管設計**，直接將底層基礎設施託管於 Google Cloud 平台，保障了生產級的高可用性與資料耐久度。為了在台積電專家評審面前展現出更進一步的「企業級頂尖演進」，我們針對現有的 GCP 託管架構，提出以下**深海優化建議方案**（可直接作為簡報中的「未來展望與技術演進」章節）：

### 6.1 資料庫架構：現有 Google Cloud SQL 託管架構與唯讀副本（Read Replicas）演進
*   **現有卓越架構（已實作）**：系統已成功淘汰 K8s 自建單點資料庫，轉而採用託管的 **Google Cloud SQL for PostgreSQL**，並配置了 `cloudsql-proxy` 側車（Sidecar）以 Google 憑證與 Workload Identity 進行加密連線。同時導入了 `pgbouncer` 連線集線器，將數千個客戶端併發連線完美多路複用成極少數實體 DB 連線，展現了極高的架構成熟度。
*   **未來深海優化方案**：
    *   **資料庫讀寫分離 (Read Replicas)**：隨著壓測規模再次擴大，主管進行「多維度報表查詢（`GET /api/events/{id}/stats`）」會佔用大量 CPU。未來可一鍵在 GCP 建立 Cloud SQL **唯讀副本（Read Replicas）**。將寫入流量（回報提交）導向主庫，讀取流量（主管報表）導向唯讀庫，徹底分流高併發負載。
    *   **驗證時間點還原 (PITR, Point-in-Time Recovery)**：開啟 Cloud SQL 的自動備份與 Write-Ahead Log (WAL) 封存，確保在人為誤刪資料或遭受攻擊時，能精確還原至任意「秒」的歷史狀態。

### 6.2 快取架構：現有 Google Cloud Memorystore 託管快取與叢集擴展
*   **現有卓越架構（已實作）**：快取與高頻滑動窗口速率限制已成功接入託管的 **Google Cloud Memorystore for Redis**（VPC Peering 內網 IP 獨立連線），在高負載時提供極致的 O(1) 讀寫效能，並具備優雅降級容錯設計。
*   **未來深海優化方案**：
    *   **啟用 Redis Cluster 橫向分片**：當壓測規模拉升至數十萬人時，單一 Redis 實例可能會遇到網路吞吐量瓶頸。可將 Memorystore 升級為 **Redis Cluster 模式**，透過雜湊槽將流量均勻分片至多台實例。
    *   **配置記憶體溢出淘汰策略**：將 Memorystore 的 `maxmemory-policy` 設置為 `volatile-lru`，在快取記憶體觸頂時自動淘汰最舊的非必要快取，保障滑動窗口速率限制等核心業務 Key 絕對可用。

### 6.3 安全與金鑰管理：整合 GCP Secret Manager 與 CSI Driver
*   **當前痛點**：目前的資料庫密碼與 JWT 金鑰以 Plain K8s Secret 存儲於叢集中（Base64 編碼），在企業級安全性審查中，Base64 儲存並不等同於加密。
*   **優化方案**：導入 **Google Secret Manager** 與 **辦公室加密金鑰 (KMS)**：
    *   金鑰與資料庫密碼統一由雲端金鑰託管系統（GCP Secret Manager）進行 KMS 金鑰加密儲存。
    *   透過 Secrets Store CSI 驅動程式，將 secrets 動態掛載為 Pod 內部的暫存記憶體磁碟卷（tmpfs），密碼不落地，防止密碼被 `kubectl get secret -o yaml` 輕易解碼。

### 6.4 運維架構：遷移至 Google Managed Service for Prometheus (GMP)
*   **當前痛點**：目前的 Prometheus 與 Grafana 採用叢集內自建部署，雖然完全自給自足，但在大型壓測時，Prometheus TSDB 寫入本身會消耗大量的 Pod 記憶體與磁碟 I/O，可能與業務後端搶佔節點資源。
*   **優化方案**：採用 **Google Cloud Managed Service for Prometheus (GMP)**：
    *   **無伺服器監控 (Serverless Scrape)**：由 Google 託管的 Monarch 代為處理億級指標的儲存與水平擴展，開發人員只需部署極輕量的 collector，無需維護 Prometheus 儲存硬碟。
    *   **統一觀測**：結合 Google Cloud Observability 儀表板，將 GKE、Cloud SQL 與 Redis 監控統一整合成 PromQL 查詢面板，提供企業級 Single Pane of Glass 觀測體驗。
