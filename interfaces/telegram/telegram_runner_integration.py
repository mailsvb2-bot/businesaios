
from __future__ import annotations

from dataclasses import dataclass

from interfaces.telegram.telegram_action_models import (
    TelegramIncomingMessage,
    TelegramOutgoingMessage,
)
from interfaces.telegram.telegram_handler import TelegramHandler
from interfaces.telegram.telegram_update_loop import TelegramUpdateLoop


@dataclass(frozen=True)
class TelegramRunnerIntegration:
    application_service: object | None = None
    decision_core: object | None = None

    def handle_updates(
        self,
        updates: list[TelegramIncomingMessage],
    ) -> list[TelegramOutgoingMessage]:
        loop = TelegramUpdateLoop(
            handler=TelegramHandler(
                application_service=self.application_service,
                decision_core=self.decision_core,
            ),
        )
        return loop.process_updates(updates)
