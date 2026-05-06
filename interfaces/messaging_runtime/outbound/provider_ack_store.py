from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderAckRecord:
    provider_message_id: str
    dedupe_key: str
    channel: str
    status: str


class ProviderAckStore:
    def __init__(self) -> None:
        self._records: dict[str, ProviderAckRecord] = {}

    def get(self, provider_message_id: str) -> ProviderAckRecord | None:
        return self._records.get(provider_message_id)

    def put(self, record: ProviderAckRecord) -> None:
        self._records[record.provider_message_id] = record
