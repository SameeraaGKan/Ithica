#!/usr/bin/env bash
# After editing backend/data/lore_seed.json: copy it into the extension (offline fallback) and re-load Atlas.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c "import json; json.load(open('backend/data/lore_seed.json'))" && echo "lore JSON valid"
cp backend/data/lore_seed.json extension/lore_seed.json && echo "copied to extension/ (reload it in chrome://extensions)"
if [ -n "${MONGODB_URI:-}" ]; then (cd backend && python3 -m scripts.load_lore); else echo "skip Atlas (MONGODB_URI not set)"; fi
echo "If relic IDs changed, re-seed Tiger too:  (cd backend && python3 -m scripts.seed_tiger)"
