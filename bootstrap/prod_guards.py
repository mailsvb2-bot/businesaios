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
    base = osp.basename(sys.argv[0] or '')
    if base and base not in {'main.py'}:
        raise RuntimeError(f'PROD_STRICT_ENTRYPOINT:{base}')
    run_mode = env_str('RUN_MODE', '').lower().strip()
    if run_mode and run_mode != 'telegram':
        raise RuntimeError(f'PROD_STRICT_RUN_MODE:{run_mode}')
    if not run_mode:
        raise RuntimeError('PROD_STRICT_RUN_MODE:unset')

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
