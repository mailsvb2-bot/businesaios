from __future__ import annotations

from typing import Protocol

from runtime.messaging_policy_events.event_record import MessagingPolicyEventRecord


class MessagingPolicyEventStore(Protocol):
    def append(self, record: MessagingPolicyEventRecord) -> None:
        ...

    def read(
        self,
        *,
        tenant_id: str,
        user_id: str,
        correlation_id: str,
    ) -> list[MessagingPolicyEventRecord]:
        ...
