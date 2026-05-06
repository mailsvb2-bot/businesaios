from __future__ import annotations

from runtime.platform.config.env_flags import env_str


def is_telegram_mode() -> bool:
    return env_str("RUN_MODE", "demo").lower().strip() == "telegram"
