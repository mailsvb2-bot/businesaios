from __future__ import annotations

from .stores import ConversationCheckpoint


class ConversationCheckpointService:
    def __init__(self, *, store) -> None:
        self._store = store

    def save_after_pipeline(self, *, message, outbound) -> None:
        self._store.save(
            ConversationCheckpoint(
                user_id=message.user_id,
                channel=message.channel,
                correlation_id=message.correlation_id,
                last_inbound_message_id=message.message_id,
                last_outbound_dedupe_key=outbound.dedupe_key,
                metadata={"body": outbound.body},
            )
        )
