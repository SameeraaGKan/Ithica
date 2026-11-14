#!/usr/bin/env bash
# One-command redeploy on the VM:  bash /opt/ithica/backend/deploy/deploy.sh [branch]
set -euo pipefail
BRANCH=${1:-main}
cd /opt/ithica && git fetch origin "$BRANCH" && git checkout "$BRANCH" && git reset --hard "origin/$BRANCH"
cd backend && .venv/bin/pip install -q -r requirements.txt
systemctl restart ithaca && sleep 2
curl -fsS http://127.0.0.1:8000/health && echo && echo "deployed $BRANCH"
