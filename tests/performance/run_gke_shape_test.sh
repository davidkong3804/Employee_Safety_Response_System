#!/usr/bin/env bash
#
# GKE shape-driven load test — drives the LoadTestShape in locustfile.py
# to produce a smooth linear (or exponential) ramp against the live GKE
# stack and saves an HTML + CSV report set ready for the demo deck.
#
# Designed to run from a GCE VM in the same region as the cluster
# (asia-east1) so RTT to https://employee-safety.duckdns.org is sub-10ms
# and a single 4-vCPU host can drive ~1500 RPS.
#
# Usage from the VM (after `./setup_loadtest_vm.sh`):
#   ./run_gke_shape_test.sh
#   SHAPE=exp PEAK_USERS=800 RAMP_SEC=180 HOLD_SEC=240 ./run_gke_shape_test.sh
#
set -u

HOST="${HOST:-https://employee-safety.duckdns.org}"
SHAPE="${SHAPE:-linear}"
PEAK_USERS="${PEAK_USERS:-500}"
RAMP_SEC="${RAMP_SEC:-120}"
HOLD_SEC="${HOLD_SEC:-180}"
SAFETY_MARGIN="${SAFETY_MARGIN:-30}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCUSTFILE="$SCRIPT_DIR/locustfile.py"
TS="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="$SCRIPT_DIR/reports/gke_shape_${SHAPE}_${TS}"
mkdir -p "$REPORT_DIR"

ulimit -n 65536 2>/dev/null || ulimit -n 10240 2>/dev/null || true

if ! command -v locust >/dev/null 2>&1; then
  echo "ERROR: 'locust' not found on PATH. Run setup_loadtest_vm.sh first."
  exit 1
fi
if ! curl -sf "$HOST/health" >/dev/null 2>&1; then
  echo "ERROR: $HOST/health is not reachable from this VM."
  exit 1
fi

RUN_TIME=$(( RAMP_SEC + HOLD_SEC + SAFETY_MARGIN ))

echo "=== GKE shape-driven load test ==="
echo "host       : $HOST"
echo "shape      : $SHAPE   (peak=$PEAK_USERS, ramp=${RAMP_SEC}s, hold=${HOLD_SEC}s)"
echo "run-time   : ${RUN_TIME}s"
echo "reports    : $REPORT_DIR"
echo

export LOAD_TEST_SHAPE="$SHAPE"
export LOAD_TEST_PEAK_USERS="$PEAK_USERS"
export LOAD_TEST_RAMP_SEC="$RAMP_SEC"
export LOAD_TEST_HOLD_SEC="$HOLD_SEC"

locust -f "$LOCUSTFILE" \
  --headless \
  --host "$HOST" \
  --run-time "${RUN_TIME}s" \
  --html "$REPORT_DIR/report.html" \
  --csv "$REPORT_DIR/report" \
  --only-summary \
  2>&1 | tee "$REPORT_DIR/locust.log"

echo
echo "=== Done ==="
echo "HTML report : $REPORT_DIR/report.html"
echo "CSV stats   : $REPORT_DIR/report_stats.csv"
echo "Pull back to local with:"
echo "  gcloud compute scp --recurse <VM_NAME>:$REPORT_DIR ./local-reports/ --zone <ZONE>"
