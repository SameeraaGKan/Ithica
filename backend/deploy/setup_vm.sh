#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu Vultr VM (run as root):  bash deploy/setup_vm.sh https://github.com/SameeraaGKan/Ithica.git
set -euo pipefail
REPO=${1:-https://github.com/SameeraaGKan/Ithica.git}
apt-get update -y && apt-get install -y python3-venv python3-pip git debian-keyring debian-archive-keyring apt-transport-https curl ffmpeg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
apt-get update -y && apt-get install -y caddy
[ -d /opt/ithica ] || git clone "$REPO" /opt/ithica
cd /opt/ithica/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
cp deploy/ithaca.service /etc/systemd/system/ithaca.service
cp deploy/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload && systemctl enable --now ithaca && systemctl reload caddy
echo "Now: edit /opt/ithica/backend/.env and /etc/caddy/Caddyfile (domain), then run deploy/deploy.sh"
