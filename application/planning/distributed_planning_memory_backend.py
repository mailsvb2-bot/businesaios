from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from core.tenancy.normalization import require_tenant_id


CANON_DISTRIBUTED_PLANNING_MEMORY_BACKEND = True


class PlanningMemoryDocumentPort(Protocol):
    def get(self, *, document_id: str) -> Mapping[str, Any] | None: ...
    def put(self, *, document_id: str, payload: Mapping[str, Any], expected_version: int | None = None) -> int: ...


@dataclass(frozen=True)
class PlanningMemorySnapshot:
    tenant_id: str
    business_id: str
    goal_plan: Mapping[str, Any]
    strategy_memory: Mapping[str, Any]
    multi_goal_queue: Mapping[str, Any]
    version: int = 0
    updated_at_utc: str = ""

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.business_id or "").strip():
            raise ValueError("business_id is required")

    @property
    def document_id(self) -> str:
        return f"{self.tenant_id}:{self.business_id}"

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "goal_plan": dict(self.goal_plan),
            "strategy_memory": dict(self.strategy_memory),
            "multi_goal_queue": dict(self.multi_goal_queue),
            "version": int(self.version),
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def empty(cls, *, tenant_id: str, business_id: str) -> "PlanningMemorySnapshot":
        return cls(
            tenant_id=require_tenant_id(tenant_id),
            business_id=str(business_id).strip(),
            goal_plan={},
            strategy_memory={},
            multi_goal_queue={},
            version=0,
            updated_at_utc="",
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PlanningMemorySnapshot":
        snapshot = cls(
            tenant_id=require_tenant_id(payload.get("tenant_id")),
            business_id=str(payload.get("business_id") or "").strip(),
            goal_plan=dict(payload.get("goal_plan") or {}),
            strategy_memory=dict(payload.get("strategy_memory") or {}),
            multi_goal_queue=dict(payload.get("multi_goal_queue") or {}),
            version=max(0, int(payload.get("version") or 0)),
            updated_at_utc=str(payload.get("updated_at_utc") or ""),
        )
        snapshot.validate()
        return snapshot


class DistributedPlanningMemoryBackend:
    def __init__(self, port: PlanningMemoryDocumentPort) -> None:
        self._port = port

    def load(self, *, tenant_id: str, business_id: str) -> PlanningMemorySnapshot:
        payload = self._port.get(document_id=f"{require_tenant_id(tenant_id)}:{str(business_id).strip()}")
        if payload is None:
            return PlanningMemorySnapshot.empty(tenant_id=tenant_id, business_id=business_id)
        return PlanningMemorySnapshot.from_dict(payload)

    def save(self, snapshot: PlanningMemorySnapshot) -> PlanningMemorySnapshot:
        snapshot.validate()
        current_payload = self._port.get(document_id=snapshot.document_id)
        current_version = 0 if current_payload is None else int(current_payload.get("version") or 0)
        stamped = PlanningMemorySnapshot(
            tenant_id=snapshot.tenant_id,
            business_id=snapshot.business_id,
            goal_plan=dict(snapshot.goal_plan),
            strategy_memory=dict(snapshot.strategy_memory),
            multi_goal_queue=dict(snapshot.multi_goal_queue),
            version=current_version + 1,
            updated_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        persisted_version = self._port.put(
            document_id=stamped.document_id,
            payload=stamped.to_dict(),
            expected_version=None if current_payload is None else current_version,
        )
        return PlanningMemorySnapshot.from_dict({**stamped.to_dict(), "version": persisted_version})

    def merge_feedback(
        self,
        *,
        tenant_id: str,
        business_id: str,
        goal_plan_patch: Mapping[str, Any] | None = None,
        strategy_patch: Mapping[str, Any] | None = None,
        multi_goal_patch: Mapping[str, Any] | None = None,
    ) -> PlanningMemorySnapshot:
        current = self.load(tenant_id=tenant_id, business_id=business_id)
        merged = PlanningMemorySnapshot(
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            goal_plan={**dict(current.goal_plan), **dict(goal_plan_patch or {})},
            strategy_memory={**dict(current.strategy_memory), **dict(strategy_patch or {})},
            multi_goal_queue={**dict(current.multi_goal_queue), **dict(multi_goal_patch or {})},
        )
        return self.save(merged)


__all__ = [
    "CANON_DISTRIBUTED_PLANNING_MEMORY_BACKEND",
    "DistributedPlanningMemoryBackend",
    "PlanningMemoryDocumentPort",
    "PlanningMemorySnapshot",
]
