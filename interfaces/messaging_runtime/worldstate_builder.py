from __future__ import annotations

from .contracts import MessageEnvelope, WorldStateInput


class CanonicalWorldStateBuilder:
    def __init__(self, build_state) -> None:
        self._build_state = build_state

    def build(self, message: MessageEnvelope):
        return self._build_state(
            WorldStateInput(
                user_id=message.user_id,
                channel=message.channel,
                correlation_id=message.correlation_id,
                message_text=message.text,
            )
        )
