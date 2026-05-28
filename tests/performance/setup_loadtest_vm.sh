#!/usr/bin/env bash
#
# Bootstrap a fresh GCE VM (Debian/Ubuntu) into a Locust load-test driver.
# Idempotent — safe to re-run.
#
# The VM does NOT need access to the private GitHub repo. The caller scp's
# locustfile.py + run_gke_shape_test.sh onto the VM after this script runs.
#
# Usage on the VM:
#   sudo bash setup_loadtest_vm.sh
#
set -euo pipefail

LOCUST_VERSION="${LOCUST_VERSION:-2.34.0}"
WORK_DIR="${WORK_DIR:-/opt/loadtest}"

echo "=== apt update / install deps ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv ca-certificates curl

echo "=== prepare $WORK_DIR ==="
mkdir -p "$WORK_DIR/tests/performance" "$WORK_DIR/reports"
chown -R $(logname 2>/dev/null || echo $SUDO_USER):$(logname 2>/dev/null || echo $SUDO_USER) "$WORK_DIR" 2>/dev/null || true

echo "=== install Locust $LOCUST_VERSION in /opt/locust-venv ==="
python3 -m venv /opt/locust-venv
/opt/locust-venv/bin/pip install --upgrade pip
/opt/locust-venv/bin/pip install "locust==$LOCUST_VERSION" requests

# Make locust easily callable for the load-runner user.
ln -sf /opt/locust-venv/bin/locust /usr/local/bin/locust

echo "=== raise file-descriptor limits ==="
cat > /etc/security/limits.d/loadtest.conf <<'EOF'
*  soft  nofile  65536
*  hard  nofile  65536
EOF

# pam_limits is usually wired in for SSH already; just make sure systemd
# sessions also pick up a high default.
mkdir -p /etc/systemd/system.conf.d
cat > /etc/systemd/system.conf.d/loadtest.conf <<'EOF'
[Manager]
DefaultLimitNOFILE=65536
EOF

echo
echo "=== Setup complete ==="
echo "Work dir: $WORK_DIR"
echo "Locust  : $(locust --version 2>&1 | head -1)"
echo
echo "Next (run from your laptop):"
echo "  gcloud compute scp tests/performance/locustfile.py tests/performance/run_gke_shape_test.sh \\"
echo "    loadtest-driver:$WORK_DIR/tests/performance/ --zone=asia-east1-a"
echo "  gcloud compute ssh loadtest-driver --zone=asia-east1-a \\"
echo "    --command 'cd $WORK_DIR && chmod +x tests/performance/*.sh && ./tests/performance/run_gke_shape_test.sh'"
