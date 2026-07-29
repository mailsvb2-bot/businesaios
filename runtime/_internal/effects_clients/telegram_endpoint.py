"""Canonical Telegram Bot API endpoint construction.

No entrypoint, action, or transport client may keep its own default host or URL
assembly. Environment overrides and token/method path construction terminate
here so all Telegram modes address the same provider endpoint.
"""

from __future__ import annotations

from runtime.platform.config.env_flags import env_str

DEFAULT_TELEGRAM_API_BASE = "https://api.telegram.org"
CANON_TELEGRAM_ENDPOINT_OWNER = True


def telegram_api_base() -> str:
    return env_str("TELEGRAM_API_BASE", DEFAULT_TELEGRAM_API_BASE).strip().rstrip("/")


def telegram_bot_base(token: str) -> str:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        raise ValueError("telegram token is required")
    return f"{telegram_api_base()}/bot{normalized_token}"


def telegram_method_url(token: str, method: str) -> str:
    normalized_method = str(method or "").strip().lstrip("/")
    if not normalized_method:
        raise ValueError("telegram method is required")
    return f"{telegram_bot_base(token)}/{normalized_method}"


def delete_webhook_fix_hint() -> str:
    """Return an operator hint using the currently resolved endpoint."""

    base = telegram_api_base()
    return (
        " | FIX (Windows CMD): python -c \"import os,requests; "
        "t=os.environ['TELEGRAM_BOT_TOKEN']; assert t; "
        f"base={base!r}; "
        "print(requests.get(f'{base}/bot{t}/deleteWebhook', "
        "params={'drop_pending_updates': True}, timeout=20).text)\""
    )


__all__ = [
    "CANON_TELEGRAM_ENDPOINT_OWNER",
    "DEFAULT_TELEGRAM_API_BASE",
    "delete_webhook_fix_hint",
    "telegram_api_base",
    "telegram_bot_base",
    "telegram_method_url",
]
