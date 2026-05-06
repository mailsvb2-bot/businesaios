from __future__ import annotations

from collections import deque

from .models import DeadLetterRecord, DeliveryAttemptState


class DurableOutboundQueueStore:
    def __init__(self) -> None:
        self._queue = deque()
        self._seen: set[str] = set()

    def put(self, envelope) -> bool:
        if envelope.dedupe_key in self._seen:
            return False
        self._queue.append(envelope)
        self._seen.add(envelope.dedupe_key)
        return True

    def get(self):
        if not self._queue:
            return None
        return self._queue.popleft()

    def size(self) -> int:
        return len(self._queue)

    def release(self, dedupe_key: str) -> None:
        self._seen.discard(dedupe_key)


class DeliveryAttemptStore:
    def __init__(self) -> None:
        self._states: dict[str, DeliveryAttemptState] = {}

    def get(self, dedupe_key: str) -> DeliveryAttemptState | None:
        return self._states.get(dedupe_key)

    def upsert(self, state: DeliveryAttemptState) -> None:
        self._states[state.dedupe_key] = state


class DeadLetterStore:
    def __init__(self) -> None:
        self._records: list[DeadLetterRecord] = []

    def put(self, record: DeadLetterRecord) -> None:
        self._records.append(record)

    def size(self) -> int:
        return len(self._records)
