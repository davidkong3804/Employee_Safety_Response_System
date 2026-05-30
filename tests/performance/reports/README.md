# Load Test Reports — 壓力測試報告導覽

Run on the GKE cluster scaled to **48 vCPU** (6× n2-standard-8) + Cloud SQL 8 vCPU ×2, with
**realistic think-time** (1–3s/user). Load generated **in-cluster** (a single laptop can't saturate
the backend — limited by ephemeral ports ~16k + WAN bandwidth). 2026-05-30.

## ⭐ Key reports (open in a browser)

| File | What it shows | Headline |
|---|---|---|
| **`15K-users-CLEAN-0.44pct-fail.html`** | The clean pass — system comfortably handles the load | **15,000 users · 0.44% fail · median 900ms · node CPU ~53%** ✅ |
| `30K-users-FINDINGS-read-conn-limit.html` | Pushed to 30k → exposed **bottleneck #1** | Read replica `max_connections=400` < 900 needed (60 pods × 15 pool, no pooler on read path) → `TooManyConnectionsError`. **Fixed** by raising to 1500. |
| `30K-users-FINDINGS-write-deadlock.html` | After fixing reads, 30k → exposed **bottleneck #2** | Write-buffer drainer runs in *every* backend pod; 60 pods batch-UPDATE the same rows → `DeadlockDetectedError`. Fix = make the drainer a singleton (leader election). |

## Key takeaway

**Hardware was over-provisioned, software was the real ceiling.** At 30k concurrent users the 48 vCPU
cluster sat at only ~40% CPU — the limits were two software/architecture issues (read-path connection
pooling, write-path drainer concurrency), both identified with concrete fixes.

## Other files in this folder
- `gke_15k_upgraded_*.html` — earlier run on the first upgrade (12 vCPU), 0.5% fail at 16k.
- `extreme_load_result.html` / `high_load_result.html` — early baseline runs.
- `ext_m4_*` (CSV) — external single-laptop attempts; hit ephemeral-port exhaustion (`OSError 49`) ~16k.
- `*stress*`, `gke_distributed_*` — superseded / intermediate runs.
