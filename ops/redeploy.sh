#!/usr/bin/env bash
# One-command redeploy on the VM:  sudo bash /opt/ithaca/ops/redeploy.sh
set -euo pipefail
APP_DIR=/opt/ithaca
sudo -u ithaca git -C "$APP_DIR" pull --ff-only
[ -f "$APP_DIR/backend/requirements.txt" ] && sudo -u ithaca "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt"
systemctl restart ithaca-api
sleep 2
curl -fsS http://127.0.0.1:8000/health && echo "  <- healthy" || { echo "HEALTH CHECK FAILED"; journalctl -u ithaca-api -n 40 --no-pager; exit 1; }
