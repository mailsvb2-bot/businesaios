from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class InboxStateStore:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def has_seen(self, message_id: str) -> bool:
        return message_id in self._seen

    def mark_seen(self, message_id: str) -> bool:
        if self.has_seen(message_id):
            return False
        self._seen.add(message_id)
        return True


@dataclass(frozen=True)
class ConversationCheckpoint:
    user_id: str
    channel: str
    correlation_id: str
    last_inbound_message_id: str
    last_outbound_dedupe_key: str | None
    metadata: Mapping[str, Any]


class ConversationCheckpointStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], ConversationCheckpoint] = {}

    def save(self, checkpoint: ConversationCheckpoint) -> None:
        self._items[(checkpoint.channel, checkpoint.user_id)] = checkpoint

    def get(self, *, channel: str, user_id: str) -> ConversationCheckpoint | None:
        return self._items.get((channel, user_id))


class IdempotencyLockStore:
    def __init__(self) -> None:
        self._locks: set[str] = set()

    def acquire(self, key: str) -> bool:
        if key in self._locks:
            return False
        self._locks.add(key)
        return True

    def release(self, key: str) -> None:
        self._locks.discard(key)
