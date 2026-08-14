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
    run_mode = env_str('RUN_MODE', env_str('APP_PROFILE', '')).lower().strip()
    if not run_mode:
        raise RuntimeError('PROD_STRICT_RUN_MODE:unset')
    allowed_profiles = {
        'api': {'entrypoint_basenames': {'run_http.py', 'run_profile.py'}, 'module_suffixes': {'entrypoints.api.run_http', 'scripts.server.run_profile'}},
        'telegram': {'entrypoint_basenames': {'main.py', 'run_profile.py'}, 'module_suffixes': {'main', 'runtime.boot.telegram_webhook_runner', 'scripts.server.run_profile'}},
        'worker': {'entrypoint_basenames': {'run_profile.py'}, 'module_suffixes': {'scripts.server.run_profile'}},
        'evolution': {'entrypoint_basenames': {'run_profile.py'}, 'module_suffixes': {'scripts.server.run_profile'}},
    }
    if run_mode not in allowed_profiles:
        raise RuntimeError(f'PROD_STRICT_RUN_MODE:{run_mode}')
    base = osp.basename(sys.argv[0] or '')
    module_name = getattr(sys.modules.get('__main__'), '__spec__', None)
    main_module = getattr(module_name, 'name', '') if module_name is not None else ''
    profile = allowed_profiles[run_mode]
    allowed_basenames = profile['entrypoint_basenames']
    allowed_modules = profile['module_suffixes']
    if base in allowed_basenames or main_module in allowed_modules:
        return
    raise RuntimeError(
        'PROD_STRICT_ENTRYPOINT:'
        f'run_mode={run_mode}:base={base or "<empty>"}:module={main_module or "<empty>"}'
    )

def _production_governance_admin_ids() -> tuple[str, ...]:
    raw = env_str('ADMIN_USER_IDS', '').strip() or env_str('ADMIN_IDS', '').strip()
    return tuple(dict.fromkeys(part.strip() for part in raw.split(',') if part.strip()))

def _telegram_governance_applies(profile: str) -> bool:
    return profile in {'telegram', 'webhook'} or (
        profile == 'api' and env_bool('TELEGRAM_WEBHOOK_ENABLED', env_bool('TELEGRAM_USE_WEBHOOK', False))
    )

def enforce_two_admins_in_prod_or_explain() -> None:
    app_env = env_str('APP_ENV', env_str('ENV', 'dev')).lower()
    if app_env != 'prod' or not env_bool('PRODUCTION_STRICT_MODE', True):
        return
    profile = env_str('RUN_MODE', env_str('APP_PROFILE', '')).lower().strip()
    if not _telegram_governance_applies(profile):
        return
    ids = _production_governance_admin_ids()
    if any(not value.isdecimal() or int(value) <= 0 for value in ids):
        raise RuntimeError('GOVERNANCE_ADMIN_IDS_INVALID')
    if env_bool('ALLOW_SELF_APPROVE', False):
        raise RuntimeError('GOVERNANCE_SELF_APPROVE_FORBIDDEN')
    mode = env_str('GOVERNANCE_ADMIN_MODE', 'dual_control').lower().strip()
    if mode == 'single_owner':
        if len(ids) != 1:
            raise RuntimeError('GOVERNANCE_SINGLE_OWNER_REQUIRED')
        return
    if mode not in {'dual_control', 'two_admins'}:
        raise RuntimeError(f'GOVERNANCE_ADMIN_MODE_INVALID:{mode}')
    if len(ids) < 2:
        raise RuntimeError('GOVERNANCE_TWO_ADMINS_REQUIRED')
