#!/usr/bin/env bash
#
# Bootstrap a fresh GCE VM (Debian/Ubuntu) into a Locust load-test driver.
# Idempotent — safe to re-run.
#
# Usage on the VM:
#   sudo bash setup_loadtest_vm.sh
#   ./tests/performance/run_gke_shape_test.sh
#
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/davidkong3804/Employee_Safety_Response_System.git}"
REPO_DIR="${REPO_DIR:-/opt/loadtest}"
LOCUST_VERSION="${LOCUST_VERSION:-2.34.0}"

echo "=== apt update / install deps ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv git ca-certificates curl

echo "=== clone or update repo at $REPO_DIR ==="
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch --depth=1 origin main
  git -C "$REPO_DIR" reset --hard origin/main
else
  rm -rf "$REPO_DIR"
  git clone --depth=1 "$REPO_URL" "$REPO_DIR"
fi

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

chmod +x "$REPO_DIR/tests/performance/run_gke_shape_test.sh" || true

echo
echo "=== Setup complete ==="
echo "Repo  : $REPO_DIR"
echo "Locust: $(locust --version 2>&1 | head -1)"
echo
echo "Next:"
echo "  cd $REPO_DIR"
echo "  ./tests/performance/run_gke_shape_test.sh"
