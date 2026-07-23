# Pewcorder production deployment
#
# Domains
# - https://api.pewcorder.benlocher.com  → Django (gunicorn :8003)
# - https://pewcorder.benlocher.com      → Vue SPA
#
# Push deploy
#   git remote add production dailyoffice:/var/repo/pewcorder.benlocher.com.git
#   git push production main
#
# Server layout
# - /var/www/api.pewcorder.benlocher.com   full checkout + .venv + backend/.env
# - /var/www/pewcorder.benlocher.com/dist  published SPA
# - /var/repo/pewcorder.benlocher.com.git  bare repo (post-receive hook)
#
# Templates in this directory are the source of truth; copy to the server
# when bootstrapping or updating nginx/systemd units.
