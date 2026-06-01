from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from application.memory.business_operating_memory import (
    BusinessMemoryPolicy,
    BusinessOperatingMemory,
    FileBusinessOperatingMemoryStore,
    canonicalize_business_memory_payload,
    project_business_memory_contract_bundle,
    project_business_memory_meta_payloads,
    project_business_memory_state_context,
)
from kernel.world_state import WorldStateV1

CANON_BUSINESS_MEMORY_STATE_ADAPTER = True


@dataclass(frozen=True)
class BusinessMemoryStateAdapter:
    store: FileBusinessOperatingMemoryStore | None = None
    policy: BusinessMemoryPolicy = field(default_factory=BusinessMemoryPolicy)

    def _rehydrate_memory(self, memory_context: dict[str, Any] | None) -> BusinessOperatingMemory:
        return canonicalize_business_memory_payload(memory_context, policy=self.policy)

    def _contract_bundle(self, memory_context: dict[str, Any] | None) -> dict[str, Any]:
        return project_business_memory_contract_bundle(memory_context, policy=self.policy)

    def _canonical_evidence_payload(self, memory_context: dict[str, Any] | None) -> dict[str, Any]:
        return dict(self._contract_bundle(memory_context).get("evidence") or {})

    def to_state_context(self, memory_context: dict[str, Any] | None) -> dict[str, Any]:
        return dict(self._contract_bundle(memory_context).get("state_context") or {})

    def inject_context(self, *, world_state: WorldStateV1, memory_context: dict[str, Any] | None) -> WorldStateV1:
        meta_payloads = project_business_memory_meta_payloads(memory_context, policy=self.policy)
        meta = dict(world_state.meta or {})
        meta.update(meta_payloads)
        return replace(world_state, meta=meta)

    def inject(self, *, world_state: WorldStateV1, tenant_id: str, business_id: str) -> WorldStateV1:
        if self.store is None:
            return world_state
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        meta_payloads = project_business_memory_meta_payloads(memory.to_evidence_payload(), policy=self.policy)
        meta = dict(world_state.meta or {})
        meta.update(meta_payloads)
        return replace(world_state, meta=meta)


__all__ = ["CANON_BUSINESS_MEMORY_STATE_ADAPTER", "BusinessMemoryStateAdapter"]
