# Deploy (Canonical)

See also: `docs/DEPLOYMENT_CONTRACT.md` (single source of truth).

## Docker Compose
1) Put `.env` next to `deploy/docker-compose.yml` (or adjust `env_file`).
2) Run:
   - `docker compose -f deploy/docker-compose.yml up -d --build`
3) Logs:
   - `docker logs -f businesaios_evolution`
   - `docker logs -f businesaios_telegram`
4) Health:
   - `http://localhost:${EVOLUTION_HEALTH_PORT:-8087}/healthz`

## systemd (Linux)
Assume app is in `/opt/businesaios` and venv in `/opt/businesaios/.venv`.
1) Copy `.env` to `/opt/businesaios/.env`
2) Run:
   - `bash deploy/systemd/install.sh`
3) Logs:
   - `journalctl -u businesaios-evolution -f`
   - `journalctl -u businesaios-telegram -f`

## Windows Task Scheduler
1) Edit paths in `deploy/windows/install_tasks.cmd`
2) Run it as Administrator.
3) Start:
   - `schtasks /Run /TN "businesaios Evolution Worker"`

## Canonical check
After installation:
- Telegram runtime calls `enqueue_evolution_job@v1`
- Outbox has pending jobs
- Worker processes -> `mark_done`
- `/healthz` shows pending decreasing to 0
