from __future__ import annotations
import sys
from pathlib import Path
from runtime.platform.config.env_flags import env_bool, env_str

def verify_release_attestation_if_needed() -> None:
    app_env = env_str('APP_ENV', env_str('ENV', 'dev')).lower()
    if app_env != 'prod' or not env_bool('RELEASE_ATTEST', True):
        return
    try:
        from runtime.security import verify_manifest
        root = Path(__file__).resolve().parents[1]
        verify_manifest(root_dir=root, manifest_path=root / 'release' / 'manifest.json')
    except Exception as e:
        raise RuntimeError(f'RELEASE_ATTESTATION_FAILED:{e}')

def enforce_production_strict_mode() -> None:
    app_env = env_str('APP_ENV', env_str('ENV', 'dev')).lower()
    if app_env != 'prod' or not env_bool('PRODUCTION_STRICT_MODE', True):
        return

    import os.path as osp

    run_mode = env_str('RUN_MODE', '').lower().strip()
    if not run_mode:
        raise RuntimeError('PROD_STRICT_RUN_MODE:unset')

    allowed_profiles = {
        'api': {
            'entrypoint_basenames': {'run_http.py'},
            'module_suffixes': {'entrypoints.api.run_http'},
        },
        'telegram': {
            'entrypoint_basenames': {'main.py'},
            'module_suffixes': {'main', 'runtime.boot.telegram_webhook_runner'},
        },
        'worker': {
            'entrypoint_basenames': {'run_profile.py'},
            'module_suffixes': {'scripts.server.run_profile'},
        },
        'evolution': {
            'entrypoint_basenames': {'run_profile.py'},
            'module_suffixes': {'scripts.server.run_profile'},
        },
    }

    if run_mode not in allowed_profiles:
        raise RuntimeError(f'PROD_STRICT_RUN_MODE:{run_mode}')

    base = osp.basename(sys.argv[0] or '')
    module_name = getattr(sys.modules.get('__main__'), '__spec__', None)
    main_module = getattr(module_name, 'name', '') if module_name is not None else ''

    profile = allowed_profiles[run_mode]
    allowed_basenames = profile['entrypoint_basenames']
    allowed_modules = profile['module_suffixes']

    if base in allowed_basenames:
        return
    if main_module in allowed_modules:
        return

    raise RuntimeError(
        'PROD_STRICT_ENTRYPOINT:'
        f'run_mode={run_mode}:base={base or "<empty>"}:module={main_module or "<empty>"}'
    )

def enforce_two_admins_in_prod_or_explain() -> None:
    app_env = env_str('APP_ENV', env_str('ENV', 'dev')).lower()
    if app_env != 'prod' or not env_bool('PRODUCTION_STRICT_MODE', True) or env_bool('ALLOW_SELF_APPROVE', False):
        return
    raw = env_str('ADMIN_USER_IDS', '').strip() or env_str('ADMIN_IDS', '').strip()
    ids = [p.strip() for p in raw.split(',') if p.strip()]
    if len(ids) >= 2:
        return
    msg = (
        '\n⛔ GOVERNANCE GUARD: требуется минимум 2 администратора.\n\n'
        'У тебя предусмотрено 2 админа. Сейчас в ADMIN_USER_IDS указан только 1 (или не указан вовсе).\n\n'
        'Добавь второго админа в .env (переменная ADMIN_USER_IDS), через запятую:\n'
        '  ADMIN_USER_IDS=123456789,987654321\n\n'
        'Для добавления админа впиши его Telegram ID в ADMIN_USER_IDS через запятую.\n\n'
        'Если ты временно один — можно включить аварийный режим (НЕ для прода):\n'
        '  ALLOW_SELF_APPROVE=1\n'
    )
    print(msg, file=sys.stderr)
    raise RuntimeError('GOVERNANCE_TWO_ADMINS_REQUIRED')
