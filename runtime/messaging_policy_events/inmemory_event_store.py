from __future__ import annotations

from threading import Lock

from runtime.messaging_policy_events.event_record import MessagingPolicyEventRecord


class InMemoryMessagingPolicyEventStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: list[MessagingPolicyEventRecord] = []

    def append(self, record: MessagingPolicyEventRecord) -> None:
        with self._lock:
            self._items.append(record)

    def read(self, *, tenant_id: str, user_id: str, correlation_id: str) -> list[MessagingPolicyEventRecord]:
        with self._lock:
            return [
                item for item in self._items
                if item.tenant_id == str(tenant_id)
                and item.user_id == str(user_id)
                and item.correlation_id == str(correlation_id)
            ]

    def iter_events(self):
        with self._lock:
            return list(self._items)
