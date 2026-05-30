# Capacity Upgrade Runbook — GKE node pool + Cloud SQL

**Goal:** raise the stack's ceiling toward ~20–30k concurrent load-test users by
(1) replacing the GKE node pool with larger machines and (2) scaling Cloud SQL up.

**Pre-condition:** the service has **no live users** (confirmed by operator), so brief
downtime during node drain and Cloud SQL restart is acceptable.

**Date:** 2026-05-29 · **Operator:** davidkong · executed step-by-step with a check after each step.

---

## 1. Current state (measured)

| Component | Current | Notes |
|---|---|---|
| GKE node pool `app-pool` | `e2-medium` (2 vCPU/~940m alloc), disk 20GB pd-standard, autoscale 2–20, **7 nodes** | zone `asia-east1-a` |
| Effective CPU ceiling | ~7.5 alloc vCPU total | capped by IP quota, see below |
| Cloud SQL `safety-db` (primary) | `db-custom-2-7680` (2 vCPU/7.5GB), **REGIONAL (HA)**, PD_SSD 10GB, private IP | POSTGRES_16 |
| Cloud SQL `safety-db-replica` | `db-custom-2-7680`, **ZONAL**, read replica of `safety-db` | |
| Backend | Deployment, HPA 3→60 @60% CPU (live), image `backend:7394cd5` | reads split to replica + Redis cache (live) |

## ✔️ UPDATE 2026-05-29 (evening): quota raised to 50 → scaled to 48 vCPU

`CPUS_ALL_REGIONS` increased **12 → 50**. Migrated the node pool again:
`app-pool-n2` (3× n2-standard-4) → **`app-pool-n2b` (6× n2-standard-8 = 48 vCPU)**, locked min=max=6.
Now 48/50 global vCPU used, IP 6/8. Cloud SQL stays db-custom-8-32768. This is **4× the 12-vCPU
right-size** and the real target for the 20–30k test — to be driven **externally** (M4 Pro laptop,
realistic think-time) so the load generator no longer competes with the backend for cluster CPU.
Node-pool cap is now 6 (7× n2-standard-8 = 56 > 50 quota).

## ✔️ Execution outcome (2026-05-29, completed) — superseded by the UPDATE above

Right-sized plan executed successfully, no downtime (backend pods did not even restart):
- **GKE:** old `app-pool` (6× e2-medium, ~6 vCPU) → new `app-pool-n2` (**3× n2-standard-4 = 12 vCPU**,
  ~11.7 alloc, dedicated cores). `CPUS_ALL_REGIONS` now 12/12.
- **Cloud SQL:** primary `safety-db` + replica `safety-db-replica` → **db-custom-8-32768** (2→8 vCPU each).
- Verified: all 18 pods Running, `/health`+`/health/ready` 200, login + `GET /api/events` OK.
- **Still NOT 20–30k capacity** — that needs the `CPUS_ALL_REGIONS` increase below. This is ~2× GKE
  compute + 4× DB compute; expect a clean report up to roughly ~3–5k concurrent.
- **Remember teardown (Phase 5)** to stop the higher 24/7 cost.

## ⚠️ BLOCKER discovered during execution (2026-05-29)

**`CPUS_ALL_REGIONS` global quota = 12 vCPU** (project-wide, all regions). Currently **6 used**
(6× e2-medium, which count as 1 vCPU each for quota), 6 free. This is the binding ceiling — it sits
*below* every other quota:

- Creating one `n2-standard-8` (8 vCPU) fails: `Insufficient project quota CPUS_ALL_REGIONS, short 2`.
- Even after deleting the whole old pool (frees 6 → 12 available), the max is **one** n2-standard-8
  (8 vCPU); a second would need 16 > 12.
- **GKE compute therefore caps at ~12 vCPU total (~2× current), nowhere near the 20–30k target.**

**Required unlock:** request a `CPUS_ALL_REGIONS` increase (e.g. 12 → 64) at
`console.cloud.google.com/iam-admin/quotas` (project `avid-vine-496920-n4`). Trial/.edu projects often
start at 8–12 and may need a billing upgrade for the increase to be granted. **The 64-vCPU target in
§3 is unreachable until this quota is raised.** Cloud SQL (Phase 2) uses a *separate* quota and is
unaffected — it can proceed independently.

## ✅ Revised plan — CHOSEN 2026-05-29 (right-size within the 12 vCPU quota)

Since `CPUS_ALL_REGIONS` can't be raised right now, target the most we can fit in 12 vCPU:

| Component | Revised target |
|---|---|
| Node pool | new `app-pool-n2`, **`n2-standard-4`** (4 vCPU/16GB) × **3 nodes** = 12 vCPU (~11.7 alloc, ~2× current) |
| Cloud SQL primary + replica | `db-custom-8-32768` (separate quota — unaffected) |

Migration sequence (respects 12-vCPU global quota + 8-IP cap; total app+system requests ≈ 2.7 vCPU
fit on one n2-standard-4 ≈ 3.9 alloc during the transition):
1. Create `app-pool-n2` n2-standard-4 **× 1** (quota 6+4=10 ≤ 12; IP 6+1=7 ≤ 8).
2. Delete old `app-pool` (6× e2-medium) → graceful drain onto the n2 node; frees 6 vCPU + 6 IPs.
3. Resize `app-pool-n2` to **3 nodes** (quota 12; IP 3).
4. Cloud SQL replica then primary → `db-custom-8-32768`.

Expected outcome: a clean load-test report at the load this scale sustains (realistically ~3–5k
concurrent), NOT 20–30k — that still needs the `CPUS_ALL_REGIONS` increase.

## 2. Hard constraints

- **External IP quota `IN_USE_ADDRESSES = 8`** (currently 7 used; each public node eats 1 IP).
  → At most **8 nodes**, and the *old + new* pool node counts must stay ≤ 8 **during** migration.
- **`E2_CPUS` quota = 24** (ambiguous enforcement: e2-medium shows 0 usage). Risky for e2-standard.
- **`N2_CPUS` quota = 200** (ample, unambiguous). → **Use `n2-standard-8`** for the new pool.
- **Cloud SQL primary is REGIONAL** → a tier change does an HA failover + restart (short blip).
- Disk quotas fine: `DISKS_TOTAL_GB` 145/2048, `SSD_TOTAL_GB` 6/250.

## 3. Target end state

| Component | Target |
|---|---|
| Node pool | new pool `app-pool-n2`, `n2-standard-8` (8 vCPU/32GB), autoscale 3–8 → up to **64 vCPU** |
| Old pool `app-pool` | **deleted** |
| Cloud SQL primary | `db-custom-8-32768` (8 vCPU/32GB) |
| Cloud SQL replica | `db-custom-8-32768` (8 vCPU/32GB) |

Machine/tier sizes are tunable; this is the working target. **Cost note:** 8× n2-standard-8 + 2×
8-vCPU Cloud SQL running 24/7 is expensive — **tear back down after the load test** (Phase 5).

---

## Phase 0 — Pre-flight checks

0.1 Confirm no traffic / locust is at 0 replicas.
0.2 Snapshot current state for rollback:
```bash
kubectl -n safety-system get deploy,sts,pvc,hpa -o wide > /tmp/pre-upgrade-state.txt
gcloud container node-pools describe app-pool --cluster safety-response --zone asia-east1-a > /tmp/pre-upgrade-pool.txt
```
0.3 Compute total pod CPU requests (must fit on ONE n2-standard-8 ≈ 7.5 alloc vCPU during migration).
0.4 Re-confirm quotas: `IN_USE_ADDRESSES` 7/8, `N2_CPUS` 0/200.

**Check:** all of the above true → proceed. If total requests > ~7 vCPU, scale down monitoring first.

---

## Phase 1 — GKE node pool migration (within the IP=8 cap)

Strategy: stand up **one** n2-standard-8 node (7 old + 1 new = 8 IPs, exactly at cap), evacuate all
workloads onto it, delete the old pool to free 7 IPs, then scale the new pool up.

1.1 **Create new pool with 1 node:**
```bash
gcloud container node-pools create app-pool-n2 \
  --cluster safety-response --zone asia-east1-a \
  --machine-type n2-standard-8 --disk-type pd-standard --disk-size 50 \
  --num-nodes 1 --enable-autoscaling --min-nodes 1 --max-nodes 8 \
  --node-labels pool=n2
```
> Disk is **pd-standard** (counts against `DISKS_TOTAL_GB` 2048, ample), NOT pd-balanced/pd-ssd —
> `SSD_TOTAL_GB` is only 250 and 8×50GB would blow it (and collide with the Cloud SQL SSD upgrade).
**Check:** new node `Ready`; `IN_USE_ADDRESSES` now 8/8; `kubectl get nodes` shows 7 e2 + 1 n2.

1.2 **Cordon all old `e2-medium` nodes** (stop new scheduling there):
```bash
kubectl cordon -l cloud.google.com/gke-nodepool=app-pool   # or cordon each old node by name
```
**Check:** old nodes `SchedulingDisabled`, n2 node schedulable.

1.3 **Drain old nodes one by one** onto the n2 node:
```bash
kubectl drain <old-node> --ignore-daemonsets --delete-emptydir-data --force --timeout=120s
```
Watch each evicted pod reschedule onto the n2 node and go `Running`. Handle PDBs/StatefulSet
(postgres-0 PVC) — same zone so the PD reattaches.
**Check after each:** no pods stuck `Pending`; backend `/health/ready` still 200 via port-forward.

1.4 **Delete the old pool** (frees 7 IPs):
```bash
gcloud container node-pools delete app-pool --cluster safety-response --zone asia-east1-a
```
**Check:** only `app-pool-n2` remains; `IN_USE_ADDRESSES` back to 1/8; all workloads `Running` on n2.

1.5 **Scale the new pool up** to target (IP budget now 8, N2 budget 200):
```bash
gcloud container clusters resize safety-response --node-pool app-pool-n2 \
  --num-nodes 4 --zone asia-east1-a   # or let HPA-driven autoscaler grow to max 8
```
**Check:** N new nodes Ready; `kubectl top nodes` shows headroom; backend HPA can now scale.

**Rollback (Phase 1):** if migration wedges, recreate an `app-pool` e2 pool and drain back; the old
pool can be re-made from `/tmp/pre-upgrade-pool.txt`. Nothing is destroyed until 1.4.

---

## Phase 2 — Cloud SQL tier upgrade

Order: **replica first, then primary** (so the read path is ready; primary change causes the failover blip).

2.1 **Upgrade the read replica:**
```bash
gcloud sql instances patch safety-db-replica --tier=db-custom-8-32768
```
**Check:** instance `RUNNABLE`; `gcloud sql instances describe safety-db-replica` shows new tier.

2.2 **Upgrade the primary (REGIONAL → failover restart):**
```bash
gcloud sql instances patch safety-db --tier=db-custom-8-32768
```
**Check:** instance `RUNNABLE`; new tier; backend reconnects (pods may log a brief connection blip).

**Rollback (Phase 2):** `gcloud sql instances patch <inst> --tier=db-custom-2-7680` reverts. Tier
changes are non-destructive (data preserved).

---

## Phase 3 — End-to-end verification

3.1 Backend health: `curl /health` and `/health/ready` (via port-forward) → 200.
3.2 Smoke test: login A001 → `GET /api/events` returns the 2 active events.
3.3 `kubectl -n safety-system get pods` — all `Running`, no `CrashLoopBackOff`/`Pending`.
3.4 HPA shows backend can scale; nodes show CPU headroom.

**Check:** all green → upgrade complete; ready for a fresh load test.

---

## Phase 4 — (later) Re-run load test

Bring locust back: `kubectl -n safety-system scale deploy/locust-master --replicas=1`,
then `locust-worker --replicas=15` (or more). Drive 20–30k via the master web API as before.

## Phase 5 — Teardown (after the demo, to stop the cost)

- Cloud SQL back to `db-custom-2-7680` (2.1/2.2 in reverse).
- Resize `app-pool-n2` back down, or recreate a small e2 pool and delete the n2 pool.
- Scale locust to 0.
