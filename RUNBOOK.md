# Runbook

## Local/Server bootstrap
1. Copy `.env.example` to `.env`.
2. Fill `APP_ENV`, `RUN_MODE`, `TENANT_ID`, `POSTGRES_DSN`, and Telegram token when using telegram mode.
3. Start Postgres and verify connectivity.
4. Run `python scripts/healthcheck.py` after HTTP surface is up, or use the runtime health port.
5. For local smoke use `RUN_MODE=demo python main.py`.
6. For production use Docker Compose and verify `/health` plus restart persistence.

## Minimum release checks
- `python -m compileall -q .`
- `pytest`
- release manifest present and current
- no `.log`, `.jsonl`, cache, or local DB artifacts tracked in git


## Webhook mode

Use webhook mode when the bot is behind HTTPS and reverse proxy. Minimal contract:

- `RUN_MODE=telegram`
- `TELEGRAM_USE_WEBHOOK=1`
- `TELEGRAM_WEBHOOK_ENABLED=1`
- `TELEGRAM_WEBHOOK_SECRET=<random high-entropy secret>`
- `TELEGRAM_WEBHOOK_URL=https://your-domain.example/telegram/webhook`
- `TELEGRAM_WEBHOOK_PATH=/telegram/webhook`
- `TELEGRAM_WEBHOOK_PORT=8080`

Start with `python main.py` or `python scripts/server/run_profile.py` with `APP_PROFILE=webhook`.
