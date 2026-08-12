# Deploy (Canonical)

See `docs/DEPLOYMENT_CONTRACT.md` for the deployment source of truth.

## Linux systemd — canonical production server path

Assume the repository is in `/opt/businesaios`, the virtualenv is `/opt/businesaios/.venv`, and production environment files live under `/etc/businesaios/`.

Core runtime:

```bash
sudo APP_DIR=/opt/businesaios deploy/systemd/install.sh
```

This installs and restarts:

- `businesaios-api.service`
- `businesaios-worker.service`

Enable the optional Telegram long-polling connector only when that provider is actually used:

```bash
sudo ENABLE_TELEGRAM_CONNECTOR=1 APP_DIR=/opt/businesaios deploy/systemd/install.sh
```

Useful checks:

```bash
systemctl --no-pager --full status businesaios-api.service businesaios-worker.service
curl -fsS http://127.0.0.1:${API_PORT:-8000}/health
curl -fsS http://127.0.0.1:${API_PORT:-8000}/readyz
curl -fsS http://127.0.0.1:${WORKER_HEALTH_PORT:-8087}/health
curl -fsS http://127.0.0.1:${WORKER_HEALTH_PORT:-8087}/ready
journalctl -u businesaios-api.service -n 200 --no-pager
journalctl -u businesaios-worker.service -n 200 --no-pager
```

The installer records deployment state under `/opt/businesaios/data/deployment/release_state.json` by default and removes the historical `businesaios-telegram.service` / `businesaios-evolution.service` units after the canonical core is installed successfully.

## Docker Compose

Put a production-compatible `.env` next to `deploy/docker-compose.yml` and start the channel-agnostic core:

```bash
docker compose -f deploy/docker-compose.yml up -d --build businesaios_api businesaios_worker
```

Check:

```bash
docker compose -f deploy/docker-compose.yml ps
curl -fsS http://127.0.0.1:${API_PORT:-8000}/readyz
curl -fsS http://127.0.0.1:${WORKER_HEALTH_PORT:-8087}/ready
```

If Telegram long polling is required, enable its explicit Compose profile:

```bash
docker compose -f deploy/docker-compose.yml --profile telegram up -d --build
```

Webhook-based providers remain attached to the API/provider-webhook runtime; do not create an always-on service for each messenger.

## Release acceptance

A server release is accepted only when:

1. the deployed Git SHA/tag is the intended release;
2. migrations complete successfully;
3. `businesaios-api.service` and `businesaios-worker.service` are active (or their Compose equivalents are healthy);
4. API `/health` and `/readyz` are successful;
5. worker `/health` and `/ready` are successful;
6. recent service logs contain no startup crash loop;
7. the canonical post-deploy smoke/user journey succeeds.

Do not use the historical `RUN_MODE=telegram/evolution` pair as the platform deployment model. Those names remain only as internal compatibility implementation details behind `scripts.server.run_profile`.
