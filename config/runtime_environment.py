from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.app_settings import AppSettings
from config.env_flags import env_bool_flag, env_int_flag, env_str_flag
from config.environment_matrix import EnvironmentMatrix, normalize_environment_name
from config.http_settings import HTTPSettings
from config.telegram_settings import TelegramSettings
from core.tenancy.normalization import normalize_tenant_id

CANON_COMPAT_SHIM = True

_TELEGRAM_TOKEN_ENV = 'TELEGRAM_' + 'BOT_TOKEN'


CANON_RUNTIME_ENVIRONMENT = True


@dataclass(frozen=True)
class RuntimeFlags:
    retention_enabled: bool = False
    marketing_bandit_enabled: bool = False
    llm_enabled: bool = False
    autopricing_enabled: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            'retention_enabled': self.retention_enabled,
            'marketing_bandit_enabled': self.marketing_bandit_enabled,
            'llm_enabled': self.llm_enabled,
            'autopricing_enabled': self.autopricing_enabled,
        }


@dataclass(frozen=True)
class RuntimeEnvironment:
    app_env: str
    run_mode: str
    tenant_id: str
    log_level: str
    structured_logs: bool

    @property
    def normalized_app_env(self) -> str:
        return normalize_environment_name(self.app_env)

    @property
    def normalized_tenant_id(self) -> str:
        return normalize_tenant_id(self.tenant_id)

    @property
    def is_production(self) -> bool:
        return self.normalized_app_env == 'prod'

    @property
    def is_headless(self) -> bool:
        return self.run_mode == 'headless'

    def matrix_row(self, matrix: EnvironmentMatrix | None = None):
        effective_matrix = matrix or EnvironmentMatrix.default()
        return effective_matrix.require(self.app_env)



def _normalized_str_flag(name: str, default: str = '') -> str:
    return (env_str_flag(name, default) or default).strip()



def _normalized_lower_flag(*names: tuple[str, str] | str, default: str) -> str:
    values: list[str] = []
    for item in names:
        if isinstance(item, tuple):
            key, fallback = item
            values.append(_normalized_str_flag(key, fallback))
        else:
            values.append(_normalized_str_flag(item, ''))
    values.append(default)
    for value in values:
        normalized = str(value or '').strip().lower()
        if normalized:
            return normalized
    return default



def load_runtime_flags() -> RuntimeFlags:
    return RuntimeFlags(
        retention_enabled=env_bool_flag('RETENTION_ENABLED', False),
        marketing_bandit_enabled=env_bool_flag('MARKETING_BANDIT_ENABLED', False),
        llm_enabled=env_bool_flag('LLM_ENABLED', False),
        autopricing_enabled=env_bool_flag('AUTOPRICING_ENABLED', False),
    )



def load_app_settings() -> AppSettings:
    if hasattr(AppSettings, 'from_env'):
        return AppSettings.from_env()  # type: ignore[attr-defined]
    environment = normalize_environment_name(_normalized_lower_flag('APP_ENV', ('ENV', 'dev'), default='dev'))
    return AppSettings(environment=environment)



def load_http_settings() -> HTTPSettings:
    if hasattr(HTTPSettings, 'from_env'):
        return HTTPSettings.from_env()  # type: ignore[attr-defined]
    return HTTPSettings(
        host=_normalized_str_flag('HTTP_HOST', '127.0.0.1') or '127.0.0.1',
        port=env_int_flag('HTTP_PORT', 8000),
        enable_auth=env_bool_flag('HTTP_ENABLE_AUTH', False),
        auth_token=_normalized_str_flag('HTTP_AUTH_TOKEN', ''),
        requests_per_minute=env_int_flag('HTTP_REQUESTS_PER_MINUTE', 60),
    )



def load_telegram_settings() -> TelegramSettings:
    if hasattr(TelegramSettings, 'from_env'):
        return TelegramSettings.from_env()  # type: ignore[attr-defined]
    return TelegramSettings(
        bot_token=_normalized_str_flag(_TELEGRAM_TOKEN_ENV, ''),
        polling_enabled=env_bool_flag('TELEGRAM_POLLING_ENABLED', False),
        webhook_enabled=env_bool_flag('TELEGRAM_WEBHOOK_ENABLED', False),
        webhook_secret=_normalized_str_flag('TELEGRAM_WEBHOOK_SECRET', ''),
    )



def load_runtime_environment() -> RuntimeEnvironment:
    return RuntimeEnvironment(
        app_env=_normalized_lower_flag('APP_ENV', ('ENV', 'dev'), default='dev'),
        run_mode=_normalized_lower_flag('RUN_MODE', ('MODE', 'demo'), default='demo'),
        tenant_id=normalize_tenant_id(_normalized_str_flag('TENANT_ID', '')),
        log_level=(_normalized_str_flag('LOG_LEVEL', 'INFO') or 'INFO').upper(),
        structured_logs=env_bool_flag('STRUCTURED_LOGS', False),
    )



def read_setting(name: str, default: Any = None) -> Any:
    key = str(name or '').strip().upper()
    if not key:
        return default
    if isinstance(default, bool) or key.endswith('_ENABLED'):
        return env_bool_flag(key, bool(default) if default is not None else False)
    if isinstance(default, int) or key.endswith(('_PORT', '_TTL', '_COUNT')):
        return env_int_flag(key, int(default) if default is not None else 0)
    return env_str_flag(key, '' if default is None else str(default))


__all__ = [
    'CANON_RUNTIME_ENVIRONMENT',
    'RuntimeEnvironment',
    'RuntimeFlags',
    'load_app_settings',
    'load_http_settings',
    'load_runtime_environment',
    'load_runtime_flags',
    'load_telegram_settings',
    'read_setting',
]
