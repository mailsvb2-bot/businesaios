#!/usr/bin/env bash
set -Eeuo pipefail

SNIPPET_SRC="${SNIPPET_SRC:-deploy/nginx/snippets/businesaios-block-noise-scans.conf}"
SNIPPET_DST="${SNIPPET_DST:-/etc/nginx/snippets/businesaios-block-noise-scans.conf}"
API_CONF="${API_CONF:-/etc/nginx/sites-available/businesaios-api.conf}"
BACKUP_DIR="${BACKUP_DIR:-/root/nginx-backups}"

step() {
  printf '\n== %s ==\n' "$1"
}

if [[ $EUID -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

step "backup nginx"
mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/nginx.$(date +%Y%m%d_%H%M%S).tar.gz" /etc/nginx >/dev/null 2>&1 || true

step "install noise scan snippet"
install -D -m 0644 "$SNIPPET_SRC" "$SNIPPET_DST"

step "ensure active upstream is 8000"
if [[ -f "$API_CONF" ]]; then
  sed -i 's#proxy_pass http://127\.0\.0\.1:8090#proxy_pass http://127.0.0.1:8000#g' "$API_CONF"
fi
if [[ -L /etc/nginx/sites-enabled/businesaios-api.conf || -f /etc/nginx/sites-enabled/businesaios-api.conf ]]; then
  sed -i 's#proxy_pass http://127\.0\.0\.1:8090#proxy_pass http://127.0.0.1:8000#g' /etc/nginx/sites-enabled/businesaios-api.conf
fi

step "verify nginx"
nginx -t

step "reload nginx"
systemctl reload nginx

step "verify health"
curl -fsS http://127.0.0.1:8000/healthz >/dev/null
curl -fsS https://api.businessaios.ru/healthz >/dev/null
curl -fsS https://status.businessaios.ru/healthz >/dev/null

echo "nginx noise hardening installed"
