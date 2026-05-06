from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeTelegramAdapter:
    application_service: object

    def handle_message_action(self, action: object) -> dict:
        return self.application_service.execute_action(action)
