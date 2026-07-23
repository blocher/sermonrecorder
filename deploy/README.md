# Pewcorder production deployment

## Domains

| Host | Role |
|------|------|
| `https://api.pewcorder.benlocher.com` | Django API + admin (gunicorn `127.0.0.1:8003`) |
| `https://pewcorder.benlocher.com` | Vue SPA |

## DNS (required before Certbot / public HTTPS)

Managed in Squarespace Domains (formerly Google Domains) for `benlocher.com`.

Point both names at the dailyoffice server:

| Type | Name | Value |
|------|------|-------|
| A | `pewcorder` | `104.237.147.195` |
| A | `api.pewcorder` | `104.237.147.195` |

Remove any old records pointing at `45.55.155.69` (that host is unreachable).

After DNS propagates:

```bash
ssh dailyoffice
certbot --nginx -d pewcorder.benlocher.com -d api.pewcorder.benlocher.com
```

## Push deploy

```bash
git remote add production dailyoffice:/var/repo/pewcorder.benlocher.com.git  # once
git push production main
```

## Server layout

- `/var/www/api.pewcorder.benlocher.com` — full checkout + `backend/.venv` + `backend/.env`
- `/var/www/pewcorder.benlocher.com/dist` — published SPA
- `/var/repo/pewcorder.benlocher.com.git` — bare repo (`hooks/post-receive`)
- systemd: `pewcorder`, `pewcorder-worker`, `pewcorder-beat`
- Redis DB `1`, Postgres DB/role `pewcorder`
- Secrets: `/var/www/api.pewcorder.benlocher.com/backend/.env` (not in git)
- DB password copy (root only): `/root/pewcorder-db-credentials.txt`

Templates in this directory are the source of truth; re-copy to the server when updating nginx/systemd units.
