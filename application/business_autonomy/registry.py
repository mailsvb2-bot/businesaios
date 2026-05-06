from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence

from application.business_autonomy.contracts import BusinessCapability, CapabilityKind
from application.business_autonomy.protocol import ExternalBusinessAdapter


@dataclass(frozen=True)
class RegisteredBusinessCapabilities:
    business_id: str
    capabilities: Sequence[BusinessCapability]


class BusinessCapabilityRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, RegisteredBusinessCapabilities] = {}

    def register(self, business_id: str, capabilities: Sequence[BusinessCapability]) -> None:
        self._items[business_id] = RegisteredBusinessCapabilities(
            business_id=business_id,
            capabilities=tuple(capabilities),
        )

    def get(self, business_id: str) -> RegisteredBusinessCapabilities:
        try:
            return self._items[business_id]
        except KeyError as exc:
            raise KeyError(f"Capabilities not registered for business_id={business_id}") from exc

    def supports(self, business_id: str, kind: CapabilityKind) -> bool:
        entry = self.get(business_id)
        return any(item.kind == kind and item.enabled for item in entry.capabilities)

    def snapshot(self) -> Mapping[str, RegisteredBusinessCapabilities]:
        return dict(self._items)


class BusinessAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, ExternalBusinessAdapter] = {}

    def register(self, adapter: ExternalBusinessAdapter) -> None:
        if adapter.business_id in self._adapters:
            raise ValueError(f"Adapter already registered for business_id={adapter.business_id}")
        self._adapters[adapter.business_id] = adapter

    def get(self, business_id: str) -> ExternalBusinessAdapter:
        try:
            return self._adapters[business_id]
        except KeyError as exc:
            raise KeyError(f"Adapter not registered for business_id={business_id}") from exc
