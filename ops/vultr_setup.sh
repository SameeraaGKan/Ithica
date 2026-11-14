#!/usr/bin/env bash
# ITHACA — one-shot setup for a fresh Vultr Ubuntu 22.04/24.04 VM.
# Run as root on the VM:
#   curl -fsSL https://raw.githubusercontent.com/SameeraaGKan/Ithica/main/ops/vultr_setup.sh -o setup.sh
#   DOMAIN=api.yourdomain.com REPO=https://github.com/SameeraaGKan/Ithica.git bash setup.sh
#
# Result: Caddy serves https://$DOMAIN (auto TLS) -> uvicorn on 127.0.0.1:8000, run by systemd.
# Point a DNS A record for $DOMAIN at this VM's IP BEFORE running, or Caddy can't get a cert.
set -euo pipefail

: "${DOMAIN:?set DOMAIN, e.g. DOMAIN=api.returntoithaca.com}"
REPO="${REPO:-https://github.com/SameeraaGKan/Ithica.git}"
BRANCH="${BRANCH:-main}"
APP_DIR=/opt/ithaca
APP_MODULE="${APP_MODULE:-app.main:app}"   # run from backend/, as in backend/README.md

echo "==> packages"
apt-get update -y
apt-get install -y git python3-venv python3-pip ffmpeg debian-keyring debian-archive-keyring apt-transport-https curl ufw
if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y && apt-get install -y caddy
fi

echo "==> firewall"
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

echo "==> code"
id ithaca >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash ithaca
if [ -d "$APP_DIR/.git" ]; then git -C "$APP_DIR" pull --ff-only; else git clone -b "$BRANCH" "$REPO" "$APP_DIR"; fi
chown -R ithaca:ithaca "$APP_DIR"

echo "==> python env"
sudo -u ithaca python3 -m venv "$APP_DIR/.venv"
sudo -u ithaca "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

echo "==> env file (fill in secrets!)"
if [ ! -f /etc/ithaca.env ]; then
  cp "$APP_DIR/backend/.env.example" /etc/ithaca.env
  chmod 600 /etc/ithaca.env && chown ithaca:ithaca /etc/ithaca.env
  echo "   -> edit /etc/ithaca.env, then: systemctl restart ithaca-api"
fi

echo "==> systemd"
sed -e "s#__APP_DIR__#$APP_DIR#g" -e "s#__APP_MODULE__#$APP_MODULE#g" "$APP_DIR/ops/ithaca-api.service" > /etc/systemd/system/ithaca-api.service
systemctl daemon-reload
systemctl enable --now ithaca-api

echo "==> caddy"
sed -e "s#__DOMAIN__#$DOMAIN#g" "$APP_DIR/ops/Caddyfile" > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo
echo "Done. Check:  curl -s https://$DOMAIN/health"
echo "Logs:         journalctl -u ithaca-api -f"
echo "Redeploy:     bash $APP_DIR/ops/redeploy.sh"
