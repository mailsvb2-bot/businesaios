from __future__ import annotations

import os

CANON_SERVER_PROFILE_RUNNER = True


def _env(name: str, default: str) -> str:
    value = os.getenv(name, '').strip()
    return value or default


def _run_api() -> int:
    os.environ.setdefault('APP_PROFILE', 'api')
    os.environ.setdefault('HEALTH_HOST', '0.0.0.0')
    host = _env('API_HOST', '0.0.0.0')
    port = int(_env('API_PORT', '8000'))
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f'api_profile_requires_uvicorn:{type(exc).__name__}:{exc}') from exc

    from bootstrap.system_boot_surface import build_system_boot_surface

    surface = build_system_boot_surface()
    app = surface.http_app
    uvicorn.run(app, host=host, port=port)
    return 0


def _run_telegram() -> int:
    os.environ.setdefault('RUN_MODE', 'telegram')
    os.environ.setdefault('HEALTH_HOST', '0.0.0.0')
    os.environ.setdefault('TELEGRAM_HEALTH_PORT', _env('TELEGRAM_HEALTH_PORT', '8088'))
    from main import main as telegram_main

    telegram_main()
    return 0




def _run_webhook() -> int:
    os.environ.setdefault('RUN_MODE', 'telegram')
    os.environ.setdefault('TELEGRAM_USE_WEBHOOK', '1')
    os.environ.setdefault('TELEGRAM_WEBHOOK_ENABLED', '1')
    from main import main as telegram_main

    telegram_main()
    return 0

def _run_worker() -> int:
    os.environ.setdefault('RUN_MODE', 'evolution')
    os.environ.setdefault('EVOLUTION_ENABLED', '1')
    os.environ.setdefault('HEALTH_HOST', '0.0.0.0')
    os.environ.setdefault('EVOLUTION_HEALTH_PORT', _env('EVOLUTION_HEALTH_PORT', '8087'))
    from runtime.evolution.main import main as evolution_main

    evolution_main()
    return 0


def main() -> int:
    profile = _env('APP_PROFILE', _env('RUN_MODE', 'api')).lower()
    if profile == 'api':
        return _run_api()
    if profile == 'telegram':
        return _run_telegram()
    if profile == 'webhook':
        return _run_webhook()
    if profile in {'worker', 'evolution'}:
        return _run_worker()
    raise SystemExit(f'unsupported_server_profile:{profile}')


if __name__ == '__main__':
    raise SystemExit(main())
