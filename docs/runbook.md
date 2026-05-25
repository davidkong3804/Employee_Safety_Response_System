# Runbook — 常用叢集操作

> 「半夜被叫起來該打哪一條指令」清單。每段都可以直接 copy-paste，
> 不需要前情提要。深入解釋去 [deployment.md](deployment.md) 跟
> [operations.md](operations.md)。

前提：你已經 `gcloud auth login` 過、`kubectl` 可以連到
`safety-system` namespace（拿 GKE credentials 的指令在
[deployment.md 第 1 節](deployment.md#1-build-and-push-images)）。

---

## Scenario A — 程式碼新增了 DB 欄位 / 索引

例子：C6 在 `safety_reports` 加了三個 `*_snapshot` 欄位。
`create_all` 不會 ALTER 既有 table，所以必須在 backend rollout **之前**
把 migration 跑掉，否則所有 `SELECT * FROM safety_reports` 都會 500
（壓測時 error rate 會炸到 40–70%）。

```bash
# 1. 重跑 db-init Job（Job spec 是 immutable，先刪再 apply）
kubectl -n safety-system delete job db-init --ignore-not-found
kubectl apply -f k8s/05-db-init-job.yaml

# 2. 等 Complete（180s 通常很夠；Cloud SQL 第一次握手會慢一點）
kubectl -n safety-system wait --for=condition=complete job/db-init --timeout=180s

# 3. 看 log 確認 migration 真的有跑（重點看「Pending migrations applied」那行）
kubectl -n safety-system logs job/db-init | tail -30

# 4. 確認後再 rollout backend
kubectl -n safety-system rollout restart deployment/backend
kubectl -n safety-system rollout status  deployment/backend --timeout=180s
```

**驗證 migration 真的有生效**：

```bash
# 拿任一個 backend pod 開 psql shell
POD=$(kubectl -n safety-system get pod -l app=backend -o name | head -1)
kubectl -n safety-system exec -it "$POD" -c backend -- \
  python -c "
import asyncio
from sqlalchemy import text
from app.database import engine

async def check():
    async with engine.begin() as conn:
        r = await conn.execute(text(\"\"\"
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'safety_reports' AND column_name LIKE '%_snapshot'
        \"\"\"))
        for row in r: print(row[0])
asyncio.run(check())
"
# 期待輸出：
#   manager_id_snapshot
#   department_snapshot
#   facility_snapshot
```

---

## Scenario B — 推了新 commit 到 main，要強制 rollout

CI 會自動 build/push image 並跑 `kubectl set image`，但有時候要手動觸發
（例如 CI 卡住、或 image 標籤跟你預期的不一樣）。

```bash
# 看現在 backend 跑的是哪個 image
kubectl -n safety-system get deploy backend \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

# 切到 :latest（manifest 本來就是 :latest + imagePullPolicy: Always，
# rollout restart 會強制重拉一次 image digest）
kubectl -n safety-system rollout restart deployment/backend
kubectl -n safety-system rollout status  deployment/backend --timeout=300s

# 看 3 個 pod 真的跨 zone（topologySpreadConstraints 是 ScheduleAnyway，
# 高密度 scale-up 時可能集中，要事後確認）
kubectl -n safety-system get pod -l app=backend \
  -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,ZONE:.metadata.labels.topology\\.kubernetes\\.io/zone
```

---

## Scenario C — HPA 暴衝後想手動縮回去

例如壓測完留下 14 pods，正在等 180s stabilization window。

```bash
# 看 HPA 目前評估狀態
kubectl -n safety-system get hpa backend
kubectl -n safety-system describe hpa backend | tail -20

# 短期放寬 scale-down policy（譬如 30% / 30s），讓它快速縮回 3
kubectl -n safety-system patch hpa backend --type=merge -p '
{
  "spec": {
    "behavior": {
      "scaleDown": {
        "stabilizationWindowSeconds": 30,
        "policies": [{"type": "Percent", "value": 30, "periodSeconds": 30}]
      }
    }
  }
}'

# 等縮回去後務必還原成 manifest 的設定（180s + 10%/min），
# 不還原下次壓測會抖動
kubectl apply -f k8s/07-backend-hpa.yaml
```

---

## Scenario D — 跑 B1 / B2 壓測（單機 locust）

前提：db-init migration 已完成（Scenario A），backend pods 跑的是新 image
（Scenario B），HPA 在 stable state（Scenario C 必要時）。

```bash
cd tests/performance

# B1：38 users / 5 分鐘 / 從本機打到 GKE Ingress
locust -f locustfile.py --headless \
  --host https://employee-safety.duckdns.org \
  --users 38 --spawn-rate 5 --run-time 300s \
  --html reports/B1-$(date +%Y%m%d_%H%M%S).html

# B2：100 users stress / 2 分鐘
locust -f locustfile.py --headless \
  --host https://employee-safety.duckdns.org \
  --users 100 --spawn-rate 20 --run-time 120s \
  --html reports/B2-$(date +%Y%m%d_%H%M%S).html

# 跑完同步看 HPA 撐到多少 pod
kubectl -n safety-system get hpa backend
kubectl -n safety-system top pod -l app=backend
```

驗收門檻在 `tests/performance/locustfile.py` 的 docstring：
- p95 < 500ms (POST /report)
- 5xx error rate < 1%
- RPS > 100（read endpoints）

---

## Scenario E — pod 壞掉了，要 debug

```bash
# 看哪幾個 pod 不健康
kubectl -n safety-system get pod -l app=backend -o wide

# 拉某個 pod 的最近 100 行 log（含前一輪 crash log）
POD=<pod-name>
kubectl -n safety-system logs "$POD" --tail=100
kubectl -n safety-system logs "$POD" --previous --tail=50  # 上一次 crash

# describe 看 events（OOMKilled、ImagePullBackOff、Readiness 失敗等）
kubectl -n safety-system describe pod "$POD" | tail -40

# 進去 pod 跑 psql / curl
kubectl -n safety-system exec -it "$POD" -c backend -- /bin/sh
```

常見症狀對應：
| 症狀 | 大概是 | 修法 |
|------|--------|------|
| Pod 0/1 Ready + readinessProbe 503 | DB 不通 | 看 cloud-sql-proxy / pgbouncer log |
| Pod CrashLoopBackOff + `column ... does not exist` | migration 沒跑 | Scenario A |
| Pod OOMKilled | memory limit 不夠 | 調高 `06-backend.yaml` 的 limits.memory |
| 多個 pod 同時 readiness 失敗 | DB pool 滿了 / Cloud SQL 故障 | `kubectl top pod`、Cloud SQL Console |

---

## Scenario G — 用 Grafana 看壓測中的即時狀態

`k8s/14-prometheus.yaml` + `k8s/15-grafana.yaml` 是叢集內部的 Prometheus +
Grafana，沒有開 Ingress（不公開），都用 `kubectl port-forward` 從本機看。

```bash
# 第一次部署
kubectl apply -f k8s/14-prometheus.yaml
kubectl apply -f k8s/15-grafana.yaml
kubectl -n safety-system rollout status deployment/prometheus --timeout=120s
kubectl -n safety-system rollout status deployment/grafana    --timeout=120s

# 開 Grafana（http://localhost:3001 → admin / admin）
kubectl -n safety-system port-forward svc/grafana 3001:3000

# 另開一個 terminal 開 Prometheus（http://localhost:9090，可以打 PromQL）
kubectl -n safety-system port-forward svc/prometheus 9090:9090
```

Dashboard `Safety Response System` 會自動 provisioned，七個 panel：
RPS、4xx/5xx error rate、p95、RPS by endpoint、p50/p90/p99、健康 pod 數、
每個 pod 的 RPS（看 load balancing 平不平均）。Auto-refresh 5 秒。

**確認 Prometheus 真的有抓到 backend：**

```bash
# Prometheus targets API
kubectl -n safety-system port-forward svc/prometheus 9090:9090 &
sleep 2
curl -s http://localhost:9090/api/v1/targets | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for t in data['data']['activeTargets']:
    print(f\"{t['labels'].get('pod', '?')}: {t['health']}\")
"
# 期待：每個 backend pod 都印 'up'
```

---

## Scenario F — 緊急 rollback 到上一版

CI 用 `:<sha>` 部署，rollback 找前一個 sha 重 set image：

```bash
# 看 rollout 歷史
kubectl -n safety-system rollout history deployment/backend

# undo 到上一版（最常用）
kubectl -n safety-system rollout undo deployment/backend
kubectl -n safety-system rollout status deployment/backend --timeout=180s

# undo 到指定 revision
kubectl -n safety-system rollout undo deployment/backend --to-revision=N
```

> **注意**：rollback 不會碰 DB schema。如果新版加了欄位、舊版讀不到，
> rollback 後舊版仍能跑（多餘欄位不影響 SELECT）；但如果新版**刪了**欄位
> 或改了 enum，rollback 前要先把 schema 還原，這個系統目前還沒遇到。
