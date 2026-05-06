from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class AnalyticsDeliverySink(Protocol):
    def deliver(self, *, tenant_id: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class AnalyticsDeliveryRequest:
    tenant_id: str
    channel: str
    payload: dict[str, Any]
    metadata: dict[str, str] = field(default_factory=dict)
