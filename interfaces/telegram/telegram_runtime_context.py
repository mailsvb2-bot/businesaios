from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramRuntimeContext:
    bot_token: str
    application_service: object
