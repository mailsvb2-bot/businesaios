from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str = ""
    polling_enabled: bool = False
    webhook_enabled: bool = False
    webhook_secret: str = ""


__all__ = ["TelegramSettings"]
