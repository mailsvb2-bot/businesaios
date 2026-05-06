from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from application.memory.business_memory_matcher import BusinessMemoryMatcher
from application.memory.business_operating_memory import (
    FileBusinessOperatingMemoryStore,
    project_business_memory_contract_bundle,
)


CANON_BUSINESS_MEMORY_QUERY = True


@dataclass(frozen=True)
class BusinessMemoryQueryService:
    store: FileBusinessOperatingMemoryStore
    matcher: BusinessMemoryMatcher = BusinessMemoryMatcher()

    def get_memory(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        return dict(project_business_memory_contract_bundle(memory.to_dict()).get("evidence") or {})

    def get_summary(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        return dict(project_business_memory_contract_bundle(memory.to_dict()).get("governance_summary") or {})

    def get_recent_runs(self, *, tenant_id: str, business_id: str, limit: int = 10) -> list[dict[str, Any]]:
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        return list(project_business_memory_contract_bundle(memory.to_dict(), recent_runs_limit=limit).get("recent_runs") or [])

    def get_recurring_failures(self, *, tenant_id: str, business_id: str) -> list[dict[str, Any]]:
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        return list(dict(project_business_memory_contract_bundle(memory.to_dict()).get("patterns") or {}).get("recurring_failures") or [])

    def get_recurring_wins(self, *, tenant_id: str, business_id: str) -> list[dict[str, Any]]:
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        return list(dict(project_business_memory_contract_bundle(memory.to_dict()).get("patterns") or {}).get("recurring_wins") or [])

    def get_anti_patterns(self, *, tenant_id: str, business_id: str) -> list[dict[str, Any]]:
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        return list(dict(project_business_memory_contract_bundle(memory.to_dict()).get("patterns") or {}).get("anti_patterns") or [])

    def get_trends(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        return dict(dict(project_business_memory_contract_bundle(memory.to_dict()).get("state_context") or {}).get("trends") or {})

    def get_similar_runs(
        self,
        *,
        tenant_id: str,
        business_id: str,
        goal: str,
        profile: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        channel: str = "",
        region: str = "",
    ) -> list[dict[str, Any]]:
        memory = self.store.load(tenant_id=tenant_id, business_id=business_id)
        target = self.matcher.build_fingerprint(
            goal=goal,
            profile=dict(profile or {}),
            meta=dict(meta or {}),
            channel=channel,
            region=region,
        )
        return [asdict(item) for item in self.matcher.select_similar_runs(memory=memory, target=target)]


__all__ = ["BusinessMemoryQueryService", "CANON_BUSINESS_MEMORY_QUERY"]
