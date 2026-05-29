from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, UTC
from typing import Any, Mapping

from application.business_autonomy.contracts import (
    BusinessExecutionEvidence,
    BusinessExecutionResult,
    BusinessGoalEnvelope,
    ExecutionVerdict,
)
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from application.business_autonomy.registry import RegisteredBusinessCapabilities
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier
from application.planning.distributed_planning_memory_backend import DistributedPlanningMemoryBackend
from governance.control_plane_audit_log import GovernanceAuditEvent
from storage.distributed_evidence_audit_backend import DistributedEvidenceStore, DistributedGovernanceAuditLog
from storage.evidence_store import EvidenceRecord


@dataclass(frozen=True)
class DistributedCapabilityRegistryView:
    registry: DistributedBusinessRegistry
    tenant_id: str

    def register(self, business_id: str, capabilities) -> None:
        record = self.registry.get(self.tenant_id, business_id)
        if record is None:
            raise KeyError(f"business registry record missing: {self.tenant_id}:{business_id}")
        self.registry.register_or_update(
            type(record)(
                business_id=record.business_id,
                tenant_id=record.tenant_id,
                ownership_key=record.ownership_key,
                region=record.region,
                channel_kind=record.channel_kind,
                capabilities=tuple(capabilities),
                trust=record.trust,
                governance_enabled=record.governance_enabled,
                persistent_surfaces=record.persistent_surfaces,
                version=record.version,
                updated_at_utc=record.updated_at_utc,
            )
        )

    def get(self, business_id: str) -> RegisteredBusinessCapabilities:
        return self.registry.capability_snapshot(tenant_id=self.tenant_id, business_id=business_id)

    def supports(self, business_id: str, kind) -> bool:
        entry = self.get(business_id)
        return any(item.kind == kind and item.enabled for item in entry.capabilities)

    def snapshot(self):
        rows = self.registry.list_for_tenant(tenant_id=self.tenant_id, limit=1000)
        return {item.business_id: RegisteredBusinessCapabilities(business_id=item.business_id, capabilities=item.capabilities) for item in rows}


@dataclass(frozen=True)
class DistributedTrustRegistryView:
    registry: DistributedBusinessRegistry
    tenant_id: str

    def register(self, snapshot: BusinessTrustSnapshot) -> None:
        record = self.registry.get(self.tenant_id, snapshot.business_id)
        if record is None:
            raise KeyError(f"business registry record missing: {self.tenant_id}:{snapshot.business_id}")
        self.registry.register_or_update(
            type(record)(
                business_id=record.business_id,
                tenant_id=record.tenant_id,
                ownership_key=record.ownership_key,
                region=record.region,
                channel_kind=record.channel_kind,
                capabilities=record.capabilities,
                trust=snapshot,
                governance_enabled=record.governance_enabled,
                persistent_surfaces=record.persistent_surfaces,
                version=record.version,
                updated_at_utc=record.updated_at_utc,
            )
        )

    def get(self, business_id: str) -> BusinessTrustSnapshot:
        return self.registry.trust_snapshot(tenant_id=self.tenant_id, business_id=business_id)


@dataclass(frozen=True)
class DistributedBusinessAutonomyAudit:
    backend: DistributedGovernanceAuditLog

    def append(self, event_type: str, payload: dict) -> None:
        tenant_id = str(payload.get("tenant_id") or payload.get("business_id") or "global")
        clean_payload = {str(k): v for k, v in dict(payload).items() if k != "tenant_id"}
        self.backend.append(GovernanceAuditEvent(event_type=str(event_type), tenant_id=tenant_id, payload=clean_payload))

    def record(self, *, event_type: str, business_id: str, goal_id: str, detail: dict) -> None:
        self.append(event_type, {"business_id": business_id, "goal_id": goal_id, **dict(detail)})

    def records(self, limit: int | None = None):
        page = self.backend.read_events(tenant_id="global", limit=max(1, int(limit or 100)))
        return tuple(
            type("DistributedAuditRecord", (), {
                "event_type": item.event_type,
                "payload": item.payload,
                "created_at_utc": item.emitted_at.isoformat(),
            })
            for item in page.events
        )


@dataclass(frozen=True)
class DistributedBusinessAutonomyEvidenceStore:
    backend: DistributedEvidenceStore

    def append_result(self, result: BusinessExecutionResult) -> EvidenceRecord:
        created_at = datetime.now(UTC)
        record = EvidenceRecord(
            evidence_id=f"business-autonomy:{result.execution_id}",
            tenant_id=str(result.metadata.get("tenant_id") or result.business_id or "global"),
            scope="business_autonomy",
            run_id=str(result.execution_id),
            action_id=str(result.goal_id),
            action_type="business_autonomy_execution",
            verification_status=result.verdict.value,
            created_at=created_at,
            refs=tuple(filter(None, (result.adapter_name, result.business_id, result.goal_id))),
            payload={
                "message": result.message,
                "metrics": dict(result.metrics),
                "metadata": dict(result.metadata),
                "evidence": [
                    {
                        "event_type": item.event_type,
                        "payload": dict(item.payload),
                        "timestamp_utc": item.timestamp_utc,
                        "source": item.source,
                    }
                    for item in result.evidence
                ],
            },
            labels={"business_id": result.business_id, "goal_id": result.goal_id, "verdict": result.verdict.value},
        )
        return self.backend.append(record)

    def list_recent(self, *, tenant_id: str, limit: int = 20):
        items, _ = self.backend.list_for_tenant(tenant_id=tenant_id, limit=limit)
        return items


@dataclass(frozen=True)
class DistributedBusinessPlanningMemorySink:
    backend: DistributedPlanningMemoryBackend

    def record_execution(self, *, request: BusinessGoalEnvelope, result: BusinessExecutionResult) -> None:
        tenant_id = str(request.metadata.get("tenant_id") or result.metadata.get("tenant_id") or request.business_id or "global")
        business_id = str(request.business_id)
        goal_family = str(request.metadata.get("goal_family") or request.goal_type or "default")
        verified = result.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED}
        snapshot = self.backend.merge_feedback(
            tenant_id=tenant_id,
            business_id=business_id,
            goal_plan_patch={
                "last_goal_id": str(request.goal_id),
                "last_goal_type": str(request.goal_type),
                "last_verdict": result.verdict.value,
                "verified": verified,
            },
            strategy_patch={
                "goal_family": goal_family,
                "strategic_signal": "business_autonomy_execution",
                "last_updated_at": datetime.now(UTC).isoformat(),
            },
            multi_goal_patch={
                "active_goal_id": str(request.goal_id),
                "queue_hint": request.metadata.get("planning_horizon", "week"),
            },
        )
        return None




@dataclass(frozen=True)
class HybridBusinessPlanningMemorySink:
    distributed_sink: DistributedBusinessPlanningMemorySink
    legacy_sink: object | None = None

    def record_execution(self, *, request: BusinessGoalEnvelope, result: BusinessExecutionResult) -> None:
        self.distributed_sink.record_execution(request=request, result=result)
        if self.legacy_sink is not None and hasattr(self.legacy_sink, "record_execution"):
            self.legacy_sink.record_execution(request=request, result=result)


__all__ = [
    "DistributedBusinessAutonomyAudit",
    "DistributedBusinessAutonomyEvidenceStore",
    "DistributedBusinessPlanningMemorySink",
    "DistributedCapabilityRegistryView",
    "DistributedTrustRegistryView",
    "HybridBusinessPlanningMemorySink",
]
