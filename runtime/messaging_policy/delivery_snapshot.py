from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from runtime.messaging.channel_normalizer import normalize_channel


def _normalize_many(value) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            out.append(normalize_channel(text))
        except ValueError:
            continue
    return tuple(dict.fromkeys(out))


@dataclass(frozen=True)
class DeliverySnapshot:
    delivered: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()

    def is_delivered(self, channel: str) -> bool:
        return normalize_channel(channel) in self.delivered

    def is_failed(self, channel: str) -> bool:
        return normalize_channel(channel) in self.failed

    def is_blocked(self, channel: str) -> bool:
        return normalize_channel(channel) in self.blocked

    @staticmethod
    def from_mapping(value: Mapping[str, Any] | None) -> DeliverySnapshot:
        if not isinstance(value, Mapping):
            return DeliverySnapshot()
        return DeliverySnapshot(
            delivered=_normalize_many(value.get("delivered")),
            failed=_normalize_many(value.get("failed")),
            blocked=_normalize_many(value.get("blocked")),
        )
