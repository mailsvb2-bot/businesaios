from __future__ import annotations

CANON_COMPAT_SHIM = True

from config.app_settings import AppSettings
from config.environment_matrix import EnvironmentMatrix
from config.http_settings import HTTPSettings
from config.runtime_environment import RuntimeEnvironment
from config.system_config import SystemConfig
from config.telegram_settings import TelegramSettings


CANON_CONFIG_VALIDATION = True



def validate_app_settings(settings: AppSettings) -> AppSettings:
    if not settings.environment:
        raise ValueError('AppSettings.environment must not be empty.')

    allowed = {'dev', 'test', 'stage', 'prod'}
    if settings.environment not in allowed:
        raise ValueError(
            f"Unsupported APP_ENV '{settings.environment}'. Allowed: {sorted(allowed)}."
        )
    return settings



def validate_http_settings(settings: HTTPSettings) -> HTTPSettings:
    if not settings.host:
        raise ValueError('HTTPSettings.host must not be empty.')

    if settings.port <= 0 or settings.port > 65535:
        raise ValueError('HTTPSettings.port must be between 1 and 65535.')

    if settings.enable_auth and not settings.auth_token:
        raise ValueError('HTTP auth is enabled, but auth token is missing.')

    if settings.requests_per_minute <= 0:
        raise ValueError('HTTP requests_per_minute must be positive.')
    return settings



def validate_telegram_settings(settings: TelegramSettings) -> TelegramSettings:
    if settings.polling_enabled and settings.webhook_enabled:
        raise ValueError('Telegram polling and webhook cannot be enabled at the same time.')

    if (settings.polling_enabled or settings.webhook_enabled) and not settings.bot_token:
        raise ValueError('Telegram is enabled, but bot token is missing.')

    if settings.webhook_enabled and not settings.webhook_secret:
        raise ValueError('Telegram webhook is enabled, but webhook secret is missing.')

    if settings.webhook_enabled and settings.webhook_auto_register and not settings.webhook_url:
        raise ValueError('TELEGRAM_WEBHOOK_URL is required when webhook auto registration is enabled.')

    if settings.webhook_enabled and not settings.webhook_path:
        raise ValueError('Telegram webhook is enabled, but webhook path is missing.')

    if settings.webhook_enabled and (settings.webhook_listen_port <= 0 or settings.webhook_listen_port > 65535):
        raise ValueError('Telegram webhook listen port must be between 1 and 65535.')
    return settings



def validate_runtime_environment(
    environment: RuntimeEnvironment,
    *,
    matrix: EnvironmentMatrix | None = None,
) -> RuntimeEnvironment:
    effective_matrix = matrix or EnvironmentMatrix.default()
    effective_matrix.require(environment.app_env)
    if not environment.run_mode:
        raise ValueError('RuntimeEnvironment.run_mode must not be empty.')
    if not environment.log_level:
        raise ValueError('RuntimeEnvironment.log_level must not be empty.')
    return environment



def validate_system_config(config: SystemConfig) -> SystemConfig:
    config.validate()
    return config


__all__ = [
    'CANON_CONFIG_VALIDATION',
    'validate_app_settings',
    'validate_http_settings',
    'validate_runtime_environment',
    'validate_system_config',
    'validate_telegram_settings',
]
