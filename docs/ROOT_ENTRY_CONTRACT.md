# Root Entry Contract — BusinesAIOS

## Canonical entrypoints

- `main.py` — sovereign runtime process entrypoint for Telegram/demo runtime
- `scripts/ci/cli.py` — canonical CI gate module entrypoint via `python -m scripts.ci.cli`
- `scripts/server/run_profile.py` — server launcher for `api`, `telegram`, `worker` profiles
- `scripts/server/migrate_before_start.py` — migration-before-start entrypoint

## Canonical root config surface

- `.env.example` — only normative top-level environment contract

## Non-canonical

- ad-hoc shell snippets that bypass the module entrypoints
- extra top-level env files
- committed runtime databases, logs, or archives
