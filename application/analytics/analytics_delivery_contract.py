from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


class AnalyticsDeliverySink(Protocol):
    def deliver(self, *, tenant_id: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class AnalyticsDeliveryRequest:
    tenant_id: str
    channel: str
    payload: dict[str, Any]
    metadata: dict[str, str] = field(default_factory=dict)
