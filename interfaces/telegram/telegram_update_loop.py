from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from interfaces.telegram.telegram_action_models import (
    TelegramIncomingMessage,
    TelegramOutgoingMessage,
)
from interfaces.telegram.telegram_handler import TelegramHandler


@dataclass(frozen=True)
class TelegramUpdateLoop:
    handler: TelegramHandler

    def process_updates(
        self,
        updates: Iterable[TelegramIncomingMessage],
    ) -> list[TelegramOutgoingMessage]:
        return [self.handler.handle_message(update) for update in updates]
