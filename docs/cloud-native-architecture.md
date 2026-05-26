# 雲原生架構說明（Stage 3 後的現況）

> 這份文件用比喻 + 圖把目前系統長什麼樣、為什麼這樣設計，講給「會 Docker、聽過 K8s、但不熟 GCP 託管服務」的工程師看。
>
> 想看歷史背景與遷移過程：[architecture.md](./architecture.md)、[deployment.md](./deployment.md)。
> 想看遷移每一步發生什麼：直接看 git log（`bb942d8`、`c90561d` 兩個 commit 就是這份文件的施工紀錄）。

---

## 一句話

把員工安全回報系統的資料層**全部換成 GCP 託管服務**，並用 PgBouncer + cloud-sql-proxy 兩個中介層，讓 K8s 上的 60 個 backend pod 在大量連線時不會把 Cloud SQL 撐爆、又能透過 IAM 安全地連線、又能在資料庫主節點掛掉時自動切換到備援。

---

## 全景圖

```mermaid
flowchart LR
    subgraph Internet
        U[使用者瀏覽器]
    end

    subgraph GKE["GKE Cluster (asia-east1-a)"]
        I[Ingress<br/>8.233.75.252]
        FE[frontend Pod<br/>nginx + React SPA]
        BE[backend Pods<br/>HPA 3-60<br/>pool=10/5]
        PB[pgbouncer Pods x2<br/>transaction mode<br/>server_pool=50]
        CP[cloudsql-proxy Pods x2<br/>Workload Identity]
    end

    subgraph GCP["GCP Managed Services (VPC default, private IP)"]
        SQL[(Cloud SQL HA<br/>safety-db<br/>db-custom-2-7680<br/>multi-zone)]
        MS[(Memorystore<br/>safety-redis<br/>1GB Basic)]
    end

    U -->|HTTPS| I
    I -->|/| FE
    I -->|/api/*| BE
    BE -->|cache R/W| MS
    BE -->|DATABASE_URL<br/>@pgbouncer:5432| PB
    PB -->|POSTGRESQL_HOST<br/>cloudsql-proxy:5432| CP
    CP -->|IAM token<br/>TLS tunnel<br/>private IP| SQL
```

ASCII 版（怕 mermaid 渲染不出來）：

```
使用者
   │ HTTPS
   ▼
Ingress (8.233.75.252) ──► frontend Pod (nginx + React)
   │ /api/*
   ▼
backend Pods (3~60 個，HPA 自動擴)
   │  ├──► Memorystore (cache, private IP)
   │  └──► pgbouncer (DATABASE_URL=@pgbouncer:5432)
   │           │
   │           ▼
   │       cloudsql-proxy (Deployment, 2 pod)
   │           │  Workload Identity → IAM → TLS
   │           ▼
   │       Cloud SQL HA (private IP only, multi-zone)
```

---

## 五個關鍵設計（每個都用一個比喻講）

### 1. PgBouncer — 連線多路復用器

**問題情境**：HPA 把 backend 擴到 60 個 pod，每個 pod 開 SQLAlchemy pool=10+5overflow，就是 60 × 15 = **900 條 DB 連線**。但 PostgreSQL 預設 `max_connections=200`，這條路一定爆。

**比喻**：餐廳裡 60 個服務員，如果每個人來客人時都跑去廚房單獨講話，廚房窗口只開 200 個會塞死。所以中間放一個「點餐櫃台」，所有服務員都對櫃台講話，櫃台再幫他們**輪流**跟廚房講。

**PgBouncer 就是這個櫃台**，跑 transaction mode：
- 對 backend 端：開放最多 1000 條 client 連線（隨便進來）
- 對 Cloud SQL 端：實際只開 ~50 條 server 連線（嚴格控制）
- 在每個 transaction 結束時，server 連線會被回收給下個 client 用

backend 60 pod × 15 client conn = 900 → 經 PgBouncer 收斂到 **真實 50 條 DB 連線**。

對應檔案：[k8s/12-pgbouncer.yaml](../k8s/12-pgbouncer.yaml)

**為什麼選 Bitnami 而且是 legacy mirror**：原 yaml 用 `bitnami/pgbouncer:1.23.1`，2025/08 後 Bitnami 把所有 production tag 搬到 `bitnamilegacy/*` namespace，所以改用 `bitnamilegacy/pgbouncer:1.23.1`（contract 完全相同）。

---

### 2. cloud-sql-proxy — 身份驗證 + 加密通道

**問題情境**：Cloud SQL 只開私有 IP，不接受帳號密碼直接連（IAM-based 認證）。而且要在 VPC 內、要 TLS。

**比喻**：進公司大樓不是從馬路上直接走進辦公室，要先**員工通道**刷卡（IAM）+ 走**加密走廊**（TLS）。`cloud-sql-proxy` 就是這個身分驗證 + 通道的代理人，你跟它講明文 PostgreSQL，它幫你刷卡 + 加密丟給 Cloud SQL。

關鍵設計選擇：**Deployment 而非 backend 的 sidecar**。

對應檔案：[k8s/13-cloudsql-proxy.yaml](../k8s/13-cloudsql-proxy.yaml)

#### 為什麼不用官方推薦的 sidecar 模式？

Google 官方文件預設教你把 cloud-sql-proxy 放在 application pod 旁邊當 sidecar。但對我們不合：

```
情境 A: sidecar 模式（每個 backend pod 自帶一個 proxy）
  60 backend pod x 1 proxy 各自連 Cloud SQL = 60 sets of conns
  → 完全繞過 PgBouncer，pooling 失效

情境 B: 獨立 Deployment（我們的做法）
  60 backend pod → pgbouncer (2 pod) → cloudsql-proxy (2 pod) → Cloud SQL
  → 中間瓶頸維持在 pgbouncer 的 server_pool=50
  → Cloud SQL 只看到 50 條穩定連線
```

代價：多一跳網路 hop，但延遲約 < 1ms，跟 Cloud SQL query 本身的 5-50ms 比起來可忽略。

---

### 3. Cloud SQL HA — 跨 zone 高可用 PostgreSQL

**問題情境**：原本是 K8s 內單 pod `postgres-0` (StatefulSet) — 那台節點如果掛了，雖然 PVC 還在但 pod 要重新調度，期間整個系統 down 1-2 分鐘。災難情境（地震員工回報）這個窗口不能接受。

**比喻**：原本只有一個櫃台辦事處（postgres-0 in zone-a），改成主辦事處 + 跨城備援辦事處（asia-east1 zone-a + zone-b），主辦事處倒了 60-120 秒內自動切到備援。

設定：
- Edition: `ENTERPRISE`（注意：`ENTERPRISE_PLUS` 不支援 `db-custom-*` 自訂 tier）
- Tier: `db-custom-2-7680`（2 vCPU / 7.5 GB RAM）
- Availability: `REGIONAL`（HA 跨 zone）
- Network: `default` VPC，**private IP only**（`--no-assign-ip`）
- Connection name: `avid-vine-496920-n4:asia-east1:safety-db`

---

### 4. Memorystore — 託管 Redis，dashboard 快取的後盾

**問題情境**：manager dashboard 每 30 秒 auto-refresh，5 個 manager 同時看就是 10 RPS 重複拉「全公司未回報員工統計」這種昂貴 query。10000 人壓測時更恐怖。

**比喻**：很多人問同樣的問題，每次都跑去翻檔案太累。把答案寫在白板上（Redis），有人問就看白板，10 秒過後再翻檔案更新一次。

對應檔案：[backend/app/cache.py](../backend/app/cache.py)

設定：
- Tier: `BASIC` 1 GB（學校 demo 級，不用 HA Standard）
- Region: `asia-east1`
- Connect mode: `PRIVATE_SERVICE_ACCESS`（透過 VPC peering）
- Endpoint: `172.27.0.3:6379`

**降級設計**：[backend/app/cache.py](../backend/app/cache.py) 有 try/except — Memorystore 掛了，會 fall through 直接打 DB，**不會讓使用者看到 500**。只是 dashboard 變慢。

---

### 5. Workload Identity — pod 怎麼證明「我是誰」給 GCP

**問題情境**：cloud-sql-proxy 要叫 Cloud SQL Admin API 拿連線資訊，得有 GCP 身份。傳統做法是建一個 service account → 下載 JSON key → 塞進 K8s Secret → 掛載到 pod。**這個 JSON key 是長期憑證，外洩就完蛋**。

**比喻**：傳統做法 = 員工帶實體鑰匙，掉了被撿走就慘。Workload Identity = 員工進門時掃臉，公司即時發一張只有今天有效的臨時通行證。

機制（不需要記，知道為什麼這樣就好）：

```
K8s ServiceAccount: safety-system/cloudsql-proxy-sa
              ↕  iam.gke.io/gcp-service-account annotation
GCP ServiceAccount: safety-cloudsql-proxy@avid-vine-496920-n4.iam.gserviceaccount.com
              ↕  roles/cloudsql.client
GCP IAM: 允許這個 SA 呼叫 Cloud SQL Admin API
```

當 cloudsql-proxy pod 啟動時，它跟 node 上的 **GKE Metadata Server** 要 token，metadata server 看 pod 的 KSA 是 `cloudsql-proxy-sa`，去找對應的 GSA，從 IAM 拿一個短期 token 回來給 pod。Token 通常 1 小時就過期，自動 refresh。

啟用步驟（已做過）：
1. Cluster level: `--workload-pool=avid-vine-496920-n4.svc.id.goog`
2. Node pool level: `--workload-metadata=GKE_METADATA`（這步是 surge upgrade，會 rolling restart nodes）
3. IAM binding: `roles/iam.workloadIdentityUser` between GSA and KSA

---

## 從一個按鈕點擊到資料庫的完整旅程

舉例：員工在 mobile 上點「我安全」按鈕。

```
1. 瀏覽器 → POST https://employee-safety.duckdns.org/api/reports
   → 走 GKE Ingress (8.233.75.252)
   → 路由到 backend Service (ClusterIP 34.118.238.5)

2. Service → kube-proxy → 挑一個 backend pod
   pod 拿到請求，解 JWT (sub=user_id)

3. backend pod 處理寫入:
   a. 拿 SQLAlchemy session (從 pool=10/5 取一條 conn)
      → conn 指向 DATABASE_URL=@pgbouncer:5432

   b. asyncpg 連到 PgBouncer (cluster service "pgbouncer")
      kube-proxy 挑一個 pgbouncer pod

   c. pgbouncer 在 transaction mode 下從它的 server pool (max 50)
      取一條已存在的 conn (or 開新的)
      → conn 指向 cloudsql-proxy:5432

   d. cloud-sql-proxy:
      - 用 WI token 認證自己給 Cloud SQL Admin API
      - 開 TLS 通道到 Cloud SQL private IP (172.27.1.2)
      - 把 SQL 透傳

   e. Cloud SQL primary node 在 zone-a 收到 INSERT safety_reports
      同步寫到 zone-b standby
      回傳 SUCCESS

   f. 回傳一路往上：Cloud SQL → cloudsql-proxy → pgbouncer
      pgbouncer 在 transaction 結束時把 server conn 還回池子
      backend pod 把 session 還回 SQLAlchemy pool

4. backend pod 順便 invalidate Redis cache (dashboard 用):
   await redis.delete("dashboard:event:{event_id}")

5. backend 回 200 OK → kube-proxy → Ingress → 瀏覽器

整個鏈路在台灣到 asia-east1，正常情況約 80-150ms。
```

---

## 故障情境：每一層掛掉會怎樣

| 元件 | 掛掉影響 | 自動恢復? | 恢復時間 |
|---|---|---|---|
| 1 個 backend pod | 自動 reschedule | ✅ | ~30s |
| 整個 backend deployment | HPA 重補，service unavailable | ✅ | ~60s |
| 1 個 pgbouncer pod | Service 自動切到另一個 | ✅ | ~5s |
| 兩個 pgbouncer 都掛 | backend 拿不到 conn (timeout=30s) | ✅ pod 自動 reschedule | ~60s |
| 1 個 cloudsql-proxy pod | 同上 | ✅ | ~5s |
| Cloud SQL primary | 自動 failover 到 standby | ✅ HA 內建 | ~60-120s |
| Memorystore | backend code fallback 直接打 DB | ✅ 程式碼層處理 | 立即（變慢但可用） |
| 整個 zone-a 掛 | Cloud SQL HA 切 zone-b；backend pod 被 cluster autoscaler 重 schedule | ✅ | ~60-180s |

---

## 容易踩到的坑（這次施工中遇到的）

### A. Bitnami Docker Hub image 拉不到
2025/08 起 Bitnami 把 production tag 搬到 `bitnamilegacy/*`。改 image 名即可。

### B. Service 跟 container 同名造成環境變數衝突
我們的 Service 叫 `pgbouncer`，K8s 會把 service info 注入成 env：
```
PGBOUNCER_PORT=tcp://10.x.x.x:5432
```
但 Bitnami pgbouncer entrypoint 預期 `PGBOUNCER_PORT` 是整數，直接 crash。

修法：在 podSpec 加 `enableServiceLinks: false`。

### C. Bitnami pgbouncer 的 database alias 預設叫 `postgres`
連線時要連到 `postgres` 這個 alias，不是真實 dbname。改：在 ConfigMap 加 `PGBOUNCER_DATABASE: "safety_response"`。

### D. cloud-sql-proxy v2 預設找 public IP
我們 Cloud SQL 只開 private IP，proxy 連不到。加 `--private-ip` flag。

### E. Workload Identity 必須在 cluster + node-pool **兩層**都啟
只啟 cluster level (`workloadPool`)，pod 還是抓不到 token。要 node pool 也設 `--workload-metadata=GKE_METADATA`，這步是 surge upgrade，會 rolling restart nodes。

### F. Cloud SQL ENTERPRISE_PLUS 不支援自訂 tier
建 instance 時要明確指定 `--edition=ENTERPRISE`，否則用 ENTERPRISE_PLUS 預設，`db-custom-2-7680` 不被接受。

### G. PgBouncer transaction mode + asyncpg + SQLAlchemy 的 prepared statement 衝突
PgBouncer 在 transaction mode 把多個 client 連線多路復用到較少的 server connection。asyncpg 預設會 implicitly prepare 每個 SQL 為 named statement (`__asyncpg_stmt_N__`)，SQLAlchemy 的 asyncpg dialect 又額外維護自己的 prepared statement cache。兩個 client 共享同條 server conn 時，名字就會撞：

```
asyncpg.exceptions.DuplicatePreparedStatementError:
prepared statement "__asyncpg_stmt_4__" already exists
```

症狀很狡猾：readiness probe 間歇 200/503，平常看不出來，壓力一上來才整片失敗。修法是**兩層 cache 都關掉**，但要走對路徑：

```python
# WRONG — prepared_statement_cache_size 不是 create_async_engine 的 kwarg
# create_async_engine(url, prepared_statement_cache_size=0, ...)  # TypeError!

# 對的做法：dialect kwarg 走 URL query string
url = settings.DATABASE_URL
if "+asyncpg" in url and "prepared_statement_cache_size" not in url:
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}prepared_statement_cache_size=0"

engine = create_async_engine(
    url,
    connect_args={"statement_cache_size": 0},  # asyncpg driver cache
)
```

- `statement_cache_size` 是 **asyncpg driver** 的 kwarg → 走 `connect_args`
- `prepared_statement_cache_size` 是 **SQLAlchemy asyncpg dialect** 的 `__init__` kwarg → 必須走 URL query string

僅設 `statement_cache_size=0` **不夠** — SQLAlchemy dialect 那層 cache 預設 100。

---

## 連線數運算（驗證 PgBouncer 真的有用）

假設高峰：

```
HPA 把 backend 擴到 60 pod
每 pod 開 pool=10 + max_overflow=5 = 15 client conns
60 × 15 = 900 client conns  ──┐
                              ▼
              PgBouncer (max_client_conn=1000)
              收所有 client；transaction mode 多路復用
                              │
                              ▼
              server_pool=50 條真實 conn 到後面
                              │
                              ▼
              cloud-sql-proxy 把這 50 條透傳到 Cloud SQL

Cloud SQL 看到的並行連線 = ~50 條
db-custom-2-7680 的 max_connections 預設 ~200
所以還有 4 倍 headroom 給其他系統 / 維護工作。
```

如果哪天要再 scale，先想：
- 60 pod × 15 conn = 900 < 1000 max_client_conn → OK
- 如果 backend 要超過 66 pod，先升 `PGBOUNCER_MAX_CLIENT_CONN`
- 真實 DB 並行用量是 server_pool=50，這個是給 Cloud SQL 的壓力 ceiling

---

## 成本概觀（asia-east1）

| 元件 | Tier / 大小 | 月費 USD（粗估） |
|---|---|---|
| Cloud SQL HA `safety-db` | db-custom-2-7680, 10GB SSD, REGIONAL | ~$220 |
| Memorystore `safety-redis` | BASIC, 1 GB | ~$33 |
| Cloud SQL Auth Proxy x2 (proxy 本身免費，只計算 GKE pod 資源) | 50m CPU + 64Mi mem each | ~$1 |
| PgBouncer x2 同上 | 50m + 64Mi | ~$1 |
| GKE node pool（原本就有） | 不變 | 不變 |
| **每月增加** | | **~$255** |

按秒/小時計費，**不用就刪掉**：

```bash
# Demo 結束、確認資料不需要時：
gcloud sql instances delete safety-db   --project=avid-vine-496920-n4
gcloud redis instances delete safety-redis --region=asia-east1 --project=avid-vine-496920-n4
kubectl -n safety-system delete pvc data-postgres-0    # 舊 postgres 的 5GB PVC，目前留著當 rollback
```

---

## 維運常用指令

### 確認資料路徑健康
```bash
# Cluster 內每個 pod 都 Running 1/1
kubectl -n safety-system get pods

# 從 backend pod 端到端測試
kubectl -n safety-system exec deploy/backend -- python -c "
import asyncio, asyncpg
async def t():
    c = await asyncpg.connect('postgresql://app:<pw>@pgbouncer:5432/safety_response', statement_cache_size=0)
    print(await c.fetchval('SELECT count(*) FROM users'))
    await c.close()
asyncio.run(t())
"
```

### 看 PgBouncer 的真實連線狀況
```bash
kubectl -n safety-system exec deploy/pgbouncer -- \
  psql -h 127.0.0.1 -p 6432 -U app pgbouncer -c "SHOW POOLS;"
```

### 看 cloud-sql-proxy 在跟誰講話
```bash
kubectl -n safety-system logs -l app=cloudsql-proxy --tail=20
```

### 強制 Cloud SQL failover（測試 HA 有沒有效）
```bash
gcloud sql instances failover safety-db --project=avid-vine-496920-n4
```

---

## 為什麼這個架構就「夠雲原生」

對比一下 stage 0（最初的設計）跟 stage 3（現況）：

| 面向 | Stage 0 | Stage 3 (現況) |
|---|---|---|
| Database | StatefulSet 單 pod | Cloud SQL HA (託管 + 自動 failover) |
| Cache | Deployment 單 pod | Memorystore (託管 + 自動備份) |
| 連線管理 | 每 pod 直連 DB | PgBouncer transaction mode 多路復用 |
| 身份驗證 | 密碼塞 K8s Secret | Workload Identity (短期 IAM token) |
| 網路安全 | Public IP 直連 | Private IP only + VPC peering |
| 災難恢復 | node 掛 = 1-2 min downtime | zone 掛 = 60-120s 自動 failover |
| 擴展上限 | postgres max_connections (200) | PgBouncer 1000 client、50 server (可調) |

「雲原生」這個詞講白話就是：**不要把資料庫當作另一個 pod 養**，把它丟給雲廠商；不要把秘密當作環境變數塞，用 IAM；不要假設網路是可信的，用 mTLS 通道。Stage 3 把這三件事都做了。

---

## 衍生閱讀

- 架構決策過程 → [improvements.md](./improvements.md)
- 部署完整步驟 → [deployment.md](./deployment.md)
- 業務邏輯與 API → [api-spec.md](./api-spec.md)
- 資料模型 → [er-diagram.md](./er-diagram.md)
- 完整資料流 sequence → [sequence-diagrams.md](./sequence-diagrams.md)
- 變更紀錄 → `git log` commit `bb942d8`、`c90561d`（Stage 3 收尾）、`787464a`（groundwork）
