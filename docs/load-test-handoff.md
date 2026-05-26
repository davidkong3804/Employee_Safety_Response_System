# 壓力測試 + 雲原生需求驗證 — 接手指南

> 給接下來要做壓測 / chaos drill / 報告書寫的隊友。整份從零開始可執行，不需要前情提要。
>
> 想了解整體架構先讀 [docs/cloud-native-architecture.md](./cloud-native-architecture.md)，知道為什麼長這樣會比較好做下面的測試。

---

## 0. 上下文（30 秒看完）

系統剛從「K8s 內單 pod postgres + redis」遷到「**Cloud SQL HA + Memorystore + PgBouncer + cloud-sql-proxy**」的雲原生架構。期末作業要驗證下面四件事，每一件都對到下面 B1–B9 其中一兩個測試：

1. **效能** — 災害發生爆量時撐得住
2. **服務擴充性** — 組織架構改了不會破壞歷史報表
3. **服務可靠性** — zero downtime deploy / no SPOF / load balancing / auto scaling / self-healing
4. **實際跑出 load / stress / performance test 數據**

整個資料路徑：

```
使用者 → GKE Ingress (8.233.75.252)
          → backend (HPA 3-60 pods, pool=10/5)
              → pgbouncer (2 pods, transaction mode, server_pool=50)
                  → cloudsql-proxy (2 pods, Workload Identity)
                      → Cloud SQL HA (db-custom-2-7680, multi-zone)
              → Memorystore (1GB BASIC, 172.27.0.3:6379) ← cache 用
```

公開 host：`https://employee-safety.duckdns.org`，所有壓測都直接打這個。

---

## 1. 先把工具連起來

```bash
# 1. GKE 連線（要 gcloud 已認證、有 cluster admin）
gcloud container clusters get-credentials safety-response \
  --zone asia-east1-a --project avid-vine-496920-n4

# 2. 確認叢集狀態正常
kubectl -n safety-system get pods
# 預期看到：backend x 3、pgbouncer x 2、cloudsql-proxy x 2、frontend x 1，全部 Running 1/1

# 3. 確認 15008 個帳號已 seed 在 Cloud SQL
kubectl -n safety-system exec deploy/backend -- python -c "
import asyncio, asyncpg, os
async def t():
    c = await asyncpg.connect(os.environ['DATABASE_URL'].replace('+asyncpg', ''), statement_cache_size=0)
    print('users:', await c.fetchval('SELECT count(*) FROM users'))
asyncio.run(t())"
# 預期：15008

# 4. Locust 本機安裝
cd tests/performance
pip install locust requests   # 如果之前沒裝過
```

帳號用法：所有用戶密碼都是 `password123`，`A001-A003` admin，`M001-M005` manager，`E001-E15000` employee。

---

## 2. 開始前先補架構缺口（Phase A）

之前的 review 抓到 3 個還沒補的缺口。**這些影響可靠性測試的結果，必須先做才能跑 B5 / B6 / B7**。

| # | 檔案 | 變更 | 為什麼 |
|---|---|---|---|
| 1 | [k8s/08-frontend.yaml:22](../k8s/08-frontend.yaml) | `replicas: 1` → `2` | frontend 目前是字面意義的 SPOF。nginx 50m/64Mi，加一個近乎免費。 |
| 2 | [k8s/09-frontend-hpa.yaml](../k8s/09-frontend-hpa.yaml) | `minReplicas: 1` → `2` | 不然 HPA 低載期間又會縮回 1 |
| 3 | [k8s/06-backend.yaml](../k8s/06-backend.yaml) podSpec | 加 `terminationGracePeriodSeconds: 40` + `lifecycle.preStop` exec `sh -c "sleep 5"` | 讓 GKE NEG endpoint 先 deregister 再 SIGTERM，消除 rolling deploy 期間 0.1% 的 5xx |
| 4 | 四個 Deployment（backend / frontend / pgbouncer / cloudsql-proxy） | 加 `topologySpreadConstraints` on `topology.kubernetes.io/zone`，`maxSkew: 1`，`whenUnsatisfiable: ScheduleAnyway`，selector 對應該 Deployment 的 `app` label | 讓兩個 pod 不擠同 zone，撐單 zone 失效。比 `podAntiAffinity` 軟，不會卡 scheduling。 |

套用：

```bash
kubectl apply -f k8s/
kubectl rollout status deploy/{frontend,backend,pgbouncer,cloudsql-proxy} -n safety-system
kubectl get pods -n safety-system -o wide   # 看 NODE，每個 component 都應該跨至少 2 個 node
```

Commit message 建議 `infra(reliability): close pre-test gaps (frontend HA, preStop, topology spread)`。

---

## 3. 監控收集：開測前先把 4 個 watcher 起來

每個測試的數據都從這幾個 watcher 來，準備好再開始 B1。建議**開 4 個 terminal**：

```bash
NS=safety-system
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p tests/performance/reports/${TS}

# T1 — pod CPU/mem 每 5 秒刷新
watch -n 5 'kubectl top pods -n safety-system'

# T2 — HPA 決策過程
kubectl get hpa -n safety-system -w | tee tests/performance/reports/${TS}/hpa.log

# T3 — pod 動態（chaos / rollout 時看誰被殺、誰補上）
kubectl get pods -n safety-system -w | tee tests/performance/reports/${TS}/pods.log

# T4 — PgBouncer pool 狀態取樣（看是否有 cl_waiting 排隊）
while true; do
  date
  kubectl exec -n safety-system deploy/pgbouncer -- \
    psql -h 127.0.0.1 -p 6432 -U app -d pgbouncer -c "SHOW POOLS;" 2>/dev/null
  sleep 15
done | tee tests/performance/reports/${TS}/pgbouncer.log
```

Cloud SQL Insights 確認啟用（沒開的話進 GCP console 開）：

```bash
gcloud sql instances describe safety-db \
  --format='value(settings.insightsConfig.queryInsightsEnabled)'
```

在 **B2 / B3 / B7 峰值時** 進 GCP console 截圖：Cloud SQL → safety-db → Query Insights → 「Top queries」「Connections」面板。

---

## 4. B1 – B9 測試（cheapest → most disruptive）

每個測試都有：**Goal**（對到哪條需求）/ **Run**（指令）/ **Pass**（過的標準）/ **Capture**（要留下的證據）。

每個測試後檢查 Locust HTML，把 `tests/performance/reports/${TS}/` 整個資料夾留起來當作業繳交證據。

統一前置（每個測試 session 一次）：

```bash
HOST=https://employee-safety.duckdns.org
NS=safety-system
TS=$(date +%Y%m%d_%H%M%S)
cd tests/performance
mkdir -p reports/${TS}
```

### B1 — Load（baseline）

- **Goal**：效能（正常負載穩定）
- **Run**：
  ```bash
  locust -f locustfile.py --headless --host $HOST \
    --users 38 --spawn-rate 5 --run-time 5m \
    --html reports/${TS}/B1_load.html
  ```
- **Pass**：p95 POST /report < 500ms ・ p95 reads < 300ms ・ error rate < 0.5% ・ backend 停在 HPA min=3
- **Capture**：Locust HTML、`kubectl top pods -n $NS` 快照

### B2 — Stress（找飽和點）

- **Goal**：效能（已知 headroom）
- **Run**：三段 back-to-back，任一段 error > 5% 或 p95 > 2s 就停，那一段當 documented break point：
  ```bash
  for U in 500 2000 5000; do
    locust -f locustfile.py --headless --host $HOST \
      --users $U --spawn-rate $((U/20)) --run-time 3m \
      --html reports/${TS}/B2_stress_${U}.html
  done
  ```
- **Pass**：HPA 在飽和前已往 60 爬；瓶頸**不是** PgBouncer（`SHOW POOLS` 的 `cl_waiting` 維持低）
- **Capture**：HPA event log、PgBouncer `SHOW POOLS`、Cloud SQL Insights 截圖

### B3 — Spike / 災難爆量（核心需求 #1）

- **Goal**：效能（災害爆量處理）
- **Run**：
  ```bash
  # 額外開兩個 terminal 收集，跟 locust 同時開
  kubectl get hpa backend -n $NS -w | tee reports/${TS}/B3_hpa.log &
  kubectl get pods -n $NS -l app=backend -w | tee reports/${TS}/B3_pods.log &

  locust -f locustfile.py --headless --host $HOST \
    --users 5000 --spawn-rate 100 --run-time 6m \
    --html reports/${TS}/B3_spike.html
  # 結束後 Ctrl+C 上面兩個背景 watcher
  ```
- **Pass**：前 60s p95 < 3s、error < 5%；90s 之後 p95 < 1s、error < 1%；backend pod 數 90s 內爬到 >15
- **Capture**：上面三個檔案

### B4 — Soak（30 分鐘穩定）

- **Goal**：可靠性（無 memory leak / pool starvation）
- **Run**：
  ```bash
  locust -f locustfile.py --headless --host $HOST \
    --users 1000 --spawn-rate 50 --run-time 30m \
    --html reports/${TS}/B4_soak.html
  ```
- **Pass**：任一 backend pod memory 漲幅 < 20% ・ PgBouncer `cl_waiting` < 5 ・ 持續 error < 1%
- **Capture**：每 2 分鐘 `kubectl top pods -n $NS -l app=backend` 寫入 `reports/${TS}/B4_top.log`；每 5 分鐘 `SHOW POOLS` 寫入 `reports/${TS}/B4_pools.log`

### B5 — Zero-downtime deploy（rolling under load）

- **Goal**：可靠性（zero downtime deploy）
- **Run**：開兩個 terminal：
  ```bash
  # Terminal A：壓測
  locust -f locustfile.py --headless --host $HOST \
    --users 500 --spawn-rate 50 --run-time 4m \
    --html reports/${TS}/B5_rolling.html

  # Terminal B：等 ~30 秒後跑
  kubectl rollout restart deploy/backend -n $NS
  kubectl rollout status deploy/backend -n $NS
  ```
- **Pass**：rollout 期間 0 5xx（pre-fix #3 套上後應該真的是 0），p95 < 1s
- **Capture**：Locust 失敗表、`kubectl get events -n $NS --sort-by=.lastTimestamp | tail -30 > reports/${TS}/B5_events.log`

### B6 — Pod-kill chaos（self-healing / no SPOF）

- **Goal**：可靠性（self-healing、無 component SPOF）
- **Run**：
  ```bash
  # Terminal A：壓測
  locust -f locustfile.py --headless --host $HOST \
    --users 200 --spawn-rate 20 --run-time 6m \
    --html reports/${TS}/B6_podkill.html

  # Terminal B：依序在 t=60s / 120s / 180s 殺一個 pod
  sleep 60
  kubectl delete pod -n $NS -l app=backend --field-selector=status.phase=Running --grace-period=0 --force | head -1
  sleep 60
  kubectl delete pod -n $NS -l app=pgbouncer --grace-period=0 --force | head -1
  sleep 60
  kubectl delete pod -n $NS -l app=cloudsql-proxy --grace-period=0 --force | head -1
  ```
- **Pass**：每次殺完 30s 內補上；error 突起 < 2% 維持 < 30s；p95 60s 內回 baseline
- **Capture**：Locust 分鐘級失敗統計、`kubectl get pods -n $NS -w` log

### B7 — Cloud SQL HA failover（DB SPOF）

- **Goal**：可靠性（DB 層 HA）
- **Run**：
  ```bash
  # Terminal A：壓測
  locust -f locustfile.py --headless --host $HOST \
    --users 100 --spawn-rate 20 --run-time 8m \
    --html reports/${TS}/B7_sqlfailover.html

  # Terminal B：等 90 秒後觸發 failover
  sleep 90
  gcloud sql instances failover safety-db --project=avid-vine-496920-n4
  ```
- **Pass**：失敗窗口 ≤ 90s ・ 全部錯誤是 5xx/timeout（**不是 pod restart** — backend liveness `/health` 不查 DB，所以 readiness 會 NotReady 但 liveness 不會殺 pod）・ 自動恢復、p95 在 failover 完成後 120s 內 < 1s
- **Capture**：Locust 時戳 CSV、`kubectl describe pod -l app=backend -n $NS | grep -E "Restart|Liveness" > reports/${TS}/B7_liveness.log`（驗證沒被殺）

### B8 — Memorystore unavailable（cache 降級）

- **Goal**：可靠性（cache 不是必需路徑）
- **Run**：
  ```bash
  # Terminal A：壓測
  locust -f locustfile.py --headless --host $HOST \
    --users 100 --spawn-rate 20 --run-time 5m \
    --html reports/${TS}/B8_redis.html

  # Terminal B：開測後 30 秒讓 Memorystore 不可達
  sleep 30
  kubectl patch cm backend-config -n $NS --type merge \
    -p '{"data":{"REDIS_URL":"redis://10.255.255.1:6379"}}'
  kubectl rollout restart deploy/backend -n $NS

  # 觀察 3 分鐘後還原
  sleep 180
  kubectl patch cm backend-config -n $NS --type merge \
    -p '{"data":{"REDIS_URL":"redis://172.27.0.3:6379"}}'
  kubectl rollout restart deploy/backend -n $NS
  ```
- **Pass**：cache 中斷期間 error < 1% ・ p95 可升到 < 1.5s（dashboard 改打 DB）・ 沒有 pod restart
- **Capture**：Locust report、`kubectl logs -n $NS -l app=backend --tail=500 | grep -i redis > reports/${TS}/B8_redis_logs.log`

### B9 — Org snapshot（核心需求 #2 擴充性）

- **Goal**：擴充性（組織異動不破壞歷史報表）
- **Run**：手動 `curl` 序列，存 8 個 JSON 進 `reports/${TS}/B9_org_snapshot/`：
  1. Login A001 → `T_admin`
  2. Login E0500 → `T_emp`；`GET /api/users/me` 抓 `MGR_OLD`
  3. `POST /api/events`（as admin）→ `EVENT_OLD`
  4. `POST /api/events/$EVENT_OLD/report {status:"safe"}`（as employee）
  5. `GET /api/events/$EVENT_OLD/stats/by-department` + `.../team-status` → 存 baseline JSON
  6. Admin 把 E0500 的 manager 改成另一個（找 admin reassignment endpoint：`PATCH /api/users/{id}`）
  7. **同樣**兩個 URL 再抓一次 → 要跟 baseline JSON byte-for-byte 相等
  8. 建 `EVENT_NEW` + employee 回報 + admin 抓 by-dept stats → 要反映新的 manager
- **Pass**：第 7 步 = 第 5 步；第 8 步反映新組織。若第 7 步不同表示 snapshot column 沒被讀到，是真的 bug。
- **Capture**：兩份 JSON 對照（建議用 `diff baseline.json after_reassign.json` 證明相等）

---

## 5. 需求 ↔ 證據對照表（報告書直接拿這個用）

| 需求 | 由哪個測試證明 | 通過樣貌 |
|---|---|---|
| 效能 - 災難爆量 | B3 Spike | 90s 後 p95<1s、error<1%；backend 90s 內 >15 pods |
| 效能 - 正常負載 | B1 Load | p95 POST /report<500ms、error<0.5% |
| 效能 - 已知 headroom | B2 Stress | 文件化飽和點；瓶頸不在 PgBouncer |
| 擴充性 - 組織異動 | B9 Org snapshot | 重派 manager 後歷史 stats 不變、新事件反映新組織 |
| 擴充性 - 水平 pod scale | B3 + B2（HPA log） | HPA 3→≥30 pod 在 90s 內完成 |
| 可靠性 - zero downtime deploy | B5 Rolling | rollout 期間 0 5xx（≤0.1%）、p95<1s |
| 可靠性 - 無 component SPOF | B6 Pod-kill | 三個 component 各自殺一 pod、30s 內補上、error 突起<2% |
| 可靠性 - 無 DB SPOF | B7 SQL failover | ≤90s 失敗窗口、自動恢復、無 liveness restart |
| 可靠性 - cache 可降級 | B8 Redis drop | 中斷期間 error<1%、fallback 走 DB |
| 可靠性 - load balancing | B5+B6 + pre-fix #4 | 任何單 pod / 單 zone 死亡都還能服務 |
| 可靠性 - auto scaling | B3 HPA log | pod count 跟著負載曲線上去（也慢慢下來） |
| 可靠性 - self-healing | B6 | 被刪 pod 自動補上，無人工介入 |
| 可靠性 - 無 memory leak | B4 Soak | 30 分鐘 memory 漲幅 <20% |

---

## 6. 跑完之後省錢（重要！）

Cloud SQL HA 跟 Memorystore 是貴的部分（合計 ~$255/月，計到秒/小時）。蒐證完一定要做這步：

```bash
# 暫停 Cloud SQL（保留資料、停 compute）
gcloud sql instances patch safety-db --activation-policy=NEVER

# 或全刪
# gcloud sql instances delete safety-db

# Memorystore BASIC 沒有 stop-only，只能刪
gcloud redis instances delete safety-redis --region=asia-east1

# GKE 工作負載歸零讓 cluster autoscaler 收 node
kubectl scale -n safety-system deploy/backend deploy/frontend deploy/pgbouncer deploy/cloudsql-proxy --replicas=0
```

要回來做 demo 時：

```bash
gcloud sql instances patch safety-db --activation-policy=ALWAYS
# 重建 Memorystore（IP 會不一樣，記得 patch backend-config）
gcloud redis instances create safety-redis \
  --size=1 --region=asia-east1 --tier=basic --redis-version=redis_7_2 \
  --connect-mode=PRIVATE_SERVICE_ACCESS --network=default \
  --reserved-ip-range=google-managed-services-default \
  --project=avid-vine-496920-n4
NEW_IP=$(gcloud redis instances describe safety-redis --region=asia-east1 --format='value(host)')
kubectl patch cm backend-config -n safety-system --type merge \
  -p "{\"data\":{\"REDIS_URL\":\"redis://${NEW_IP}:6379\"}}"
kubectl scale -n safety-system deploy/backend deploy/frontend deploy/pgbouncer deploy/cloudsql-proxy --replicas=3
```

---

## 7. 卡住的時候

- **/health/ready 503 不穩**：看 [docs/cloud-native-architecture.md](./cloud-native-architecture.md) 「容易踩到的坑 G」— PgBouncer + asyncpg prepared statement 衝突。理論上 fix `af5a535` 後已經解決，但如果再現先看那一節。
- **HPA 不動**：`kubectl describe hpa backend -n safety-system` 看 events；通常是 metrics-server 還沒回報，等 30s 就好。
- **cloudsql-proxy 一直 ImagePullBackOff**：node 沒有 GKE_METADATA mode，跑 `gcloud container node-pools update app-pool --cluster=safety-response --zone=asia-east1-a --workload-metadata=GKE_METADATA --project=avid-vine-496920-n4`。
- **Locust 跑出來 connection refused**：先 curl 一下 `curl https://employee-safety.duckdns.org/health` 確認 ingress 有起，再看 backend pods 是不是都 Ready。
- **PgBouncer SHOW POOLS 怎麼讀**：`cl_active` = 正在跑 query 的 client；`cl_waiting` = 在排隊等 server conn；後者長期 > 0 表示 server_pool=50 不夠，要升或檢查 query 慢。

---

## 8. 跑完寫一份報告書

把 `tests/performance/reports/${TS}/` 整個資料夾連同對照表結果寫成 `docs/performance-reports/stage3-verification-${TS}.md`，模板：

```markdown
# Stage 3 雲原生需求驗收 — YYYY-MM-DD

## 環境
- Cluster: safety-response (asia-east1-a)
- Cloud SQL: safety-db (db-custom-2-7680, REGIONAL)
- Memorystore: safety-redis (1GB BASIC)

## 結果摘要
[對照表，每一列附 PASS / FAIL + 一句話 + Locust HTML 連結]

## 各測試 narrative
### B1 Load
[數字 + screenshot/log 連結]
...

## 觀察與限制
[ex: 5000 user 時 cloud-sql-proxy 是瓶頸 / cache hit ratio / cold start latency]

## 建議後續
[ex: 增加 cloudsql-proxy replicas、Cloud SQL tier 升級條件]
```

---

問題 / 卡住可以開 issue 在 [GitHub repo](https://github.com/davidkong3804/Employee_Safety_Response_System/issues) 標 `testing`。
