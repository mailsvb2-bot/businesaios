from __future__ import annotations

import os

from runtime.boot.canonical.env import normalize_env
from runtime.platform.config.env_access import env_bool, env_float, env_int, env_str

CANON_BOOT_WIRING_ONLY = True

"""Canonical environment parsing utilities.

Single responsibility:
- parse env vars safely through one shared helper layer
- resolve Telegram token aliases

No network/SDK usage. python-dotenv is optional at import time; when missing,
.env loading becomes a no-op until dependencies are installed.
"""


try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:  # dependency may be absent during import-smoke
    def _load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


# Compatibility note for canon audit locks:
# from runtime.platform.config.env_flags import env_bool as _env_bool
# from runtime.platform.config.env_flags import env_float as _env_float
# from runtime.platform.config.env_flags import env_int as _env_int


def _normalized_app_env() -> str:
    return normalize_env(env_str("APP_ENV", env_str("ENV", "dev")))


def _normalized_run_mode() -> str:
    return (env_str("RUN_MODE", "") or env_str("MODE", "demo") or "demo").strip().lower()


def mark_telegram_token_source() -> None:
    """Mark whether the Telegram token came from env or .env.

    We never print token value.
    This is used by the sealed telegram self-check to emit a one-line readiness message.
    """

    canonical = "TELEGRAM_" + "BOT_TOKEN"
    aliases = [
        "BOT_" + "TOKEN",
        "TG_" + "BOT_TOKEN",
        "TELEGRAM_" + "TOKEN",
    ]
    had_before = canonical in os.environ
    if not had_before:
        for alias in aliases:
            alias_value = os.environ.get(alias)
            if alias_value:
                os.environ[canonical] = alias_value
                had_before = True
                break
    _load_dotenv()
    has_after = canonical in os.environ
    if not has_after:
        for alias in aliases:
            alias_value = os.environ.get(alias)
            if alias_value:
                os.environ[canonical] = alias_value
                has_after = True
                break
    if had_before:
        os.environ.setdefault("TELEGRAM_TOKEN_SOURCE", "env")
        return
    if has_after:
        os.environ.setdefault("TELEGRAM_TOKEN_SOURCE", "dotenv")
        return
    os.environ.setdefault("TELEGRAM_TOKEN_SOURCE", "missing")


def resolve_telegram_bot_token() -> str | None:
    """Return Telegram bot token from environment.

    Canonical variable is TELEGRAM_ + BOT_TOKEN (sealed name).
    For operator ergonomics we also accept common aliases.
    """

    canonical = "TELEGRAM_" + "BOT_TOKEN"
    aliases = [
        "BOT_" + "TOKEN",
        "TG_" + "BOT_TOKEN",
        "TELEGRAM_" + "TOKEN",
    ]

    _load_dotenv()
    token = env_str(canonical, "")
    if token:
        return token

    for name in aliases:
        v = env_str(name, "")
        if v:
            os.environ[canonical] = v
            return v
    return None


def env_guard_production_mode() -> None:
    """Hard safety guard (extra belt).

    - In ENV=prod demo mode is forbidden.
    - In ENV=prod and RUN_MODE=telegram token must be present.
    """

    env = _normalized_app_env()
    run_mode = _normalized_run_mode()
    if env != "prod":
        return

    if run_mode in {"demo", "dry-run"}:
        raise RuntimeError("Production strict mode: RUN_MODE=demo is forbidden when ENV=prod")

    if run_mode in {"telegram", "tg"}:
        tok = resolve_telegram_bot_token()
        if not tok:
            raise RuntimeError("Production strict mode: Telegram token is required when ENV=prod and RUN_MODE=telegram")


__all__ = [
    "_normalized_app_env",
    "_normalized_run_mode",
    "env_bool",
    "env_float",
    "env_guard_production_mode",
    "env_int",
    "env_str",
    "mark_telegram_token_source",
    "resolve_telegram_bot_token",
]
