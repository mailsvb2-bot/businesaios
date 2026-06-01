from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str = ""
    polling_enabled: bool = False
    webhook_enabled: bool = False
    webhook_secret: str = ""
    webhook_auto_register: bool = False
    webhook_url: str = ""
    webhook_path: str = "/telegram/webhook"
    webhook_listen_host: str = "0.0.0.0"
    webhook_listen_port: int = 8080


__all__ = ["TelegramSettings"]
