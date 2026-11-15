#!/usr/bin/env bash
# ITHACA setup for macOS and Linux. Run from anywhere:  bash setup/setup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5vl:3b}"
say() { printf "\n\033[1m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[33m!! %s\033[0m\n" "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { warn "$1 is missing: $2"; MISSING=1; }; }
MISSING=0

say "Checking tools"
need python3 "install Python 3.11+ (brew install python  or  https://www.python.org)"
need node "install Node.js LTS (brew install node  or  https://nodejs.org)"
need npm "comes with Node.js"
need ffmpeg "needed for recap videos (brew install ffmpeg  or  sudo apt install ffmpeg)"
if ! command -v ollama >/dev/null 2>&1; then warn "ollama is missing: needed for the local Oracle model (brew install ollama  or  https://ollama.com)"; fi
[ "$MISSING" = 1 ] && { warn "Install the missing tools above, then run this again."; exit 1; }

say "Backend: virtual environment and Python packages"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt pytest
if [ ! -f .env ]; then cp .env.example .env; echo "created backend/.env (fill in your keys)"; fi

say "Frontend: Node packages"
cd "$ROOT/frontend"
npm ci --silent
if [ ! -f .env.local ]; then cp .env.example .env.local; echo "created frontend/.env.local"; fi

say "Local Oracle model (Ollama)"
if command -v ollama >/dev/null 2>&1; then
  listed="$(ollama list 2>/dev/null || true)"
  case "$listed" in *"$OLLAMA_MODEL"*) ;; *) ollama pull "$OLLAMA_MODEL" || warn "could not pull $OLLAMA_MODEL; start Ollama and run: ollama pull $OLLAMA_MODEL" ;; esac
fi

say "Tests"
cd "$ROOT/backend" && .venv/bin/python -m pytest -q tests || warn "some tests failed"

say "Done. Start everything with:  bash setup/dev.sh"
