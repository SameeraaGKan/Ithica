#!/usr/bin/env bash
# Start the API (port 8080) and the web app (port 3000). Ctrl+C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cleanup() { kill $(jobs -p) 2>/dev/null || true; }
trap cleanup EXIT INT TERM
(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --reload --port 8080) &
(cd "$ROOT/frontend" && NEXT_PUBLIC_API_URL=http://127.0.0.1:8080 npm run dev -- --port 3000) &
echo "API: http://127.0.0.1:8080/docs    Web: http://localhost:3000"
wait
