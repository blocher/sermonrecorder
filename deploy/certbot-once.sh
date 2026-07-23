#!/usr/bin/env bash
# Run on dailyoffice after Squarespace A records point here.
set -euo pipefail
EXPECTED=104.237.147.195
for host in pewcorder.benlocher.com api.pewcorder.benlocher.com; do
  ip="$(dig +short A "$host" | tail -1)"
  echo "$host -> ${ip:-<none>}"
  if [[ "$ip" != "$EXPECTED" ]]; then
    echo "DNS not ready (want $EXPECTED). Update Squarespace Domains A records first."
    exit 1
  fi
done
certbot --nginx \
  -d pewcorder.benlocher.com \
  -d api.pewcorder.benlocher.com \
  --non-interactive \
  --agree-tos \
  --register-unsafely-without-email
nginx -t
systemctl reload nginx
echo "TLS certificates installed."
