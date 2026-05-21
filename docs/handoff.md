# Team Handoff — Monitoring & Stress Testing

## 系統現況(讀這段就懂環境)

| 項目 | 值 |
|---|---|
| Public URL | https://employee-safety.duckdns.org (cert provisioning 中,先用 http://) |
| GCP project | `avid-vine-496920-n4` |
| GKE cluster | `safety-response` in `asia-east1-a`(zonal Standard) |
| Node pool | `app-pool`,e2-medium × 2-4(cluster autoscaler 啟用) |
| Namespace | `safety-system` |
| HPA | backend 1-30,frontend 1-10,target CPU 70% |
| Demo 帳號 | A001(admin)/ M001(manager)/ E001(employee),密碼 `password123` |
| GitHub | https://github.com/davidkong3804/Employee_Safety_Response_System |

## 兩件先做的事(共用)

1. **裝 gcloud + kubectl + gke-gcloud-auth-plugin**
   ```bash
   brew install --cask gcloud-cli
   ln -sf /opt/homebrew/Caskroom/gcloud-cli/*/google-cloud-sdk/bin/gke-gcloud-auth-plugin \
     /opt/homebrew/bin/gke-gcloud-auth-plugin
   ```
2. **拿 cluster 權限**
   ```bash
   gcloud auth login
   gcloud config set project avid-vine-496920-n4
   gcloud container clusters get-credentials safety-response --zone=asia-east1-a
   kubectl get -n safety-system pods   # 應該看到 4 個 Running pod
   ```
3. **跟 David 要 GCP IAM `Kubernetes Engine Developer` 角色**(否則 kubectl 會被擋)。

---

## 組員 A — 監控(Observability)

### 任務目標
讓 dashboard 可以看到「pods 在線數、HPA scale 事件、API p95 latency、DB 連線數」,並在出狀況時收 email 通知。

### 工具 / 知識
- **Cloud Monitoring**(GCP 內建,已自動開)— 路徑 https://console.cloud.google.com/monitoring/dashboards?project=avid-vine-496920-n4
- **Cloud Logging**(同上,已自動收 `kubectl logs` 內容)
- **Google Managed Prometheus**(免費 50GB/月)— GKE 預設啟用
- **`prometheus-fastapi-instrumentator`**(Python 套件)— 1 行 middleware 就能讓 FastAPI 自動 export `/metrics`

### 具體步驟(估時 2-3 小時)

1. **逛 GCP Monitoring 的 GKE dashboard**,熟悉現有圖表(Pod CPU/Mem、HPA replicas、Ingress 流量)。
2. **新增 FastAPI metrics export**(讓 backend 自己暴露指標)
   - `backend/requirements.txt`:加 `prometheus-fastapi-instrumentator==7.0.0`
   - `backend/app/main.py`:
     ```python
     from prometheus_fastapi_instrumentator import Instrumentator
     Instrumentator().instrument(app).expose(app)
     ```
   - 開 PR、merge → 重 build image → kubectl set image
3. **告訴 Managed Prometheus 來抓**(加 annotation 到 backend Deployment)
   - `k8s/06-backend.yaml` 的 pod template metadata 加:
     ```yaml
     annotations:
       prometheus.io/scrape: "true"
       prometheus.io/port: "8000"
       prometheus.io/path: "/metrics"
     ```
4. **建 4 個 alert**(Cloud Monitoring → Alerting → Create Policy)
   | Alert | 觸發條件 | 通知方式 |
   |---|---|---|
   | HPA 觸頂 | backend replicas = 30 持續 5 分 | Email |
   | Pod 重啟太頻繁 | restart_count 5min 內 > 3 | Email |
   | API 慢 | p95 latency > 1s 持續 3 分 | Email |
   | DB 連線太多 | pg_stat_activity count > 280 | Email |
5. **做一個自己的 dashboard**(Monitoring → Dashboards → Create),拼上面 4 個 chart。
6. 寫一份 README.md 在 `docs/monitoring.md` 紀錄怎麼看。

### 交付物
- PR:加 instrumentator + annotation
- PR:`docs/monitoring.md` 截圖 + 操作說明
- Cloud Monitoring 上 4 個 alert + 1 個 dashboard

---

## 組員 B — 壓力測試(Load Test)

### 任務目標
跑 Locust 把 backend 推到極限,觀察 HPA + cluster autoscaler 完整擴展過程,產出報告。

### 工具 / 知識
- **Locust**(Python load test 工具)— repo 內 `tests/performance/locustfile.py` 已寫好
- **`kubectl`**(看 pod / hpa / node 即時擴展)
- **Cloud Monitoring**(看 latency / CPU 隨負載變化)

### 具體步驟(估時 2-3 小時)

1. **裝 locust**:
   ```bash
   cd tests/performance
   pip install locust
   ```
2. **本地試跑(50 用戶)看 locustfile 邏輯**:
   ```bash
   locust -f locustfile.py --headless \
     --host https://employee-safety.duckdns.org \
     --users 50 --spawn-rate 5 --run-time 2m \
     --html reports/warmup.html
   ```
3. **三個 terminal 同時開**(壓測時要看現場):
   - Terminal 1: `locust ... --users 500 --spawn-rate 20 --run-time 10m --html reports/stress.html`
   - Terminal 2: `watch -n 2 kubectl get -n safety-system hpa,pods`(看 HPA 加 pod)
   - Terminal 3: `watch -n 5 kubectl get nodes`(看 CA 加 node)
4. **跑三組逐步加壓的測試**並各別產 html report:
   | 階段 | users | duration | 預期觀察 |
   |---|---|---|---|
   | warmup | 50 | 2 分 | 1 個 backend 就夠,CPU < 30% |
   | medium | 200 | 5 分 | HPA 開始 scale up,backend 達 3-5 個 |
   | stress | 500 | 10 分 | HPA 衝到 maxReplicas=30,CA 加 node 到 3-4 個 |
5. **記錄關鍵 metrics**(從 locust html + Cloud Monitoring):
   - 每階段的 p50 / p95 / p99 latency
   - 錯誤率(>1% 就是真的撐不住)
   - HPA 從 1 → max 花了幾分鐘
   - CA 加 node 花了幾分鐘
   - 撐不住時的瓶頸:CPU?memory?DB 連線?
6. **寫報告**到 `docs/stress-test-report.md`,包含上面表格 + 結論「在 X users 時 latency 飛起來,瓶頸是 Y」。

### 交付物
- PR:`tests/performance/reports/` 3 份 locust HTML
- PR:`docs/stress-test-report.md`(含瓶頸分析跟下一步建議)

---

## 共用備忘

### Git 流程
```bash
git checkout -b feature/<你的工作> main
# 改 code
git add . && git commit -m "..."
git push -u origin feature/<你的工作>
gh pr create --base main   # 或 github 網頁開 PR
# 等 CI 過,merge
```

### 本地跑系統(不上雲)
```bash
docker compose up --build -d   # backend :8000  frontend :5173
docker compose down -v         # 結束
```

### 看 GKE 上的 logs
```bash
kubectl logs -n safety-system -l app=backend --tail=100 -f
kubectl logs -n safety-system -l app=frontend --tail=100 -f
```

### scale 自己玩(練習用)
```bash
kubectl scale -n safety-system deployment/backend --replicas=5    # 注意 HPA 會復原
# 改 HPA min:
kubectl patch hpa -n safety-system backend --type=merge -p '{"spec":{"minReplicas":3}}'
```

### 預算注意
- 目前架構 idle ~$50/月,壓測尖峰 ~$100-150/月
- 不用的時候縮 cluster 省錢:`gcloud container clusters resize safety-response --zone=asia-east1-a --num-nodes=0`(LB 還是會收 ~$18/月,徹底砍掉要 `clusters delete`)

### 問問題前先看
1. `docs/architecture.md`(整體架構)
2. `docs/deployment.md`(GKE 部署細節)
3. `CLAUDE.md`(開發指南)
4. 還不懂再問 David
