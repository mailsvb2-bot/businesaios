from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from application.business_autonomy.contracts import (
    BusinessCapability,
    BusinessExecutionEvidence,
    BusinessExecutionResult,
    BusinessGoalEnvelope,
    CapabilityKind,
    ExecutionVerdict,
)
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier
from application.planning.goal_plan_memory import FileGoalPlanMemoryStore, GoalPlanMemoryService
from application.planning.long_horizon_planner import LongHorizonPlanner
from application.planning.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService
from application.planning.strategy_memory import FileStrategyMemoryStore, StrategyMemoryService
from execution.operator_override_contract import (
    OperatorOverrideResolution,
    OperatorOverrideStatus,
)
from execution.operator_override_store import build_default_operator_override_store
from governance.approval_contract import ApprovalRequest, ApprovalStatus
from governance.approval_store import build_default_approval_store
from governance.control_plane_audit_log import GovernanceAuditEvent, PersistentGovernanceAuditLog
from governance.persistence_codec import atomic_write_json, read_json_or_default
from reliability.idempotency_contract import IdempotencyResolution
from reliability.idempotency_scope import build_idempotency_key
from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore
from storage.evidence_store import EvidenceRecord, SqliteEvidenceStore
from storage.sqlite_fallback import SqliteSessionFactory

BUSINESS_AUTONOMY_OWNER_ID = "business_autonomy"


@dataclass(frozen=True)
class PersistentAuditRecord:
    event_type: str
    payload: Mapping[str, Any]
    created_at_utc: str


def _data_dir() -> Path:
    from os import getenv
    data_dir = getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir)


def business_autonomy_runtime_dir() -> Path:
    return _data_dir() / "runtime"


def business_autonomy_idempotency_store_path() -> Path:
    return business_autonomy_runtime_dir() / "business_autonomy_idempotency.sqlite3"


def business_autonomy_evidence_store_path() -> Path:
    return business_autonomy_runtime_dir() / "business_autonomy_evidence.sqlite3"


class PersistentBusinessAutonomyAudit:
    """Adapter that routes business autonomy audit to canonical governance audit persistence."""

    def __init__(self, backend: PersistentGovernanceAuditLog | None = None) -> None:
        self._backend = backend or PersistentGovernanceAuditLog()

    def append(self, event_type: str, payload: dict) -> None:
        tenant_id = str(payload.get("tenant_id") or payload.get("business_id") or "global")
        clean_payload = {str(k): v for k, v in dict(payload).items() if k != "tenant_id"}
        self._backend.append(
            GovernanceAuditEvent(
                event_type=str(event_type),
                tenant_id=tenant_id,
                payload=clean_payload,
            )
        )

    def record(self, *, event_type: str, business_id: str, goal_id: str, detail: dict) -> None:
        payload = {"business_id": business_id, "goal_id": goal_id, **dict(detail)}
        self.append(event_type, payload)

    def records(self, limit: int | None = None) -> list[PersistentAuditRecord]:
        events = self._backend.read_events()
        if limit is not None and limit >= 0:
            events = events[-int(limit):]
        return [
            PersistentAuditRecord(
                event_type=str(item.get("event_type") or "unknown"),
                payload=dict(item.get("payload") or {}),
                created_at_utc=str(item.get("emitted_at") or ""),
            )
            for item in events
        ]


class PersistentBusinessAutonomyIdempotencyStore:
    """Canonical adapter over the reliability idempotency contract.

    The reservation is acquired before any external effect. Completed results
    are replayed; in-progress and terminal failures fail closed.
    """

    def __init__(self, backend: SQLiteIdempotencyStore | None = None) -> None:
        self._backend = backend or SQLiteIdempotencyStore(business_autonomy_idempotency_store_path())
        self._owner_id = BUSINESS_AUTONOMY_OWNER_ID

    def get(self, key: str):
        idem_key = self._idem_key(key)
        record = self._backend.get(key=idem_key)
        if record is None:
            return None
        payload = record.metadata.get("business_autonomy_result")
        if not isinstance(payload, Mapping):
            return None
        return _deserialize_result(payload)

    def reserve(self, key: str, *, owner_id: str):
        from application.business_autonomy.guards import (
            BusinessIdempotencyReservation,
            BusinessIdempotencyReservationStatus,
        )

        idem_key = self._idem_key(key)
        decision = self._backend.reserve(
            key=idem_key,
            owner_id=str(owner_id),
            metadata_patch={"business_autonomy_key": str(key)},
        )
        if decision.resolution is IdempotencyResolution.ACCEPTED:
            return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.ACCEPTED)
        if decision.resolution is IdempotencyResolution.REPLAY_COMPLETED:
            payload = decision.record.metadata.get("business_autonomy_result")
            result = _deserialize_result(payload) if isinstance(payload, Mapping) else None
            return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.REPLAY_COMPLETED, result)
        if decision.resolution is IdempotencyResolution.REJECTED_IN_PROGRESS:
            return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.IN_PROGRESS)
        return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.TERMINAL_FAILED)

    def complete(self, key: str, *, owner_id: str, payload: object) -> None:
        if not isinstance(payload, BusinessExecutionResult):
            raise TypeError("business autonomy idempotency payload must be BusinessExecutionResult")
        idem_key = self._idem_key(key)
        self._backend.mark_completed(
            key=idem_key,
            owner_id=str(owner_id),
            result_ref=f"business_autonomy:{key}",
            metadata_patch={"business_autonomy_result": _serialize_result(payload)},
        )

    def fail(self, key: str, *, owner_id: str, reason: str) -> None:
        self._backend.mark_failed(
            key=self._idem_key(key),
            owner_id=str(owner_id),
            reason=str(reason),
            metadata_patch={"business_autonomy_failure": str(reason)},
        )

    def put(self, key: str, payload: object) -> None:
        """Compatibility cache for a terminal result produced before effects."""
        if not isinstance(payload, BusinessExecutionResult):
            return None
        owner_id = f"{self._owner_id}:terminal-cache"
        idem_key = self._idem_key(key)
        decision = self._backend.reserve(
            key=idem_key,
            owner_id=owner_id,
            metadata_patch={"business_autonomy_key": str(key)},
        )
        if decision.resolution is IdempotencyResolution.ACCEPTED:
            self._backend.mark_completed(
                key=idem_key,
                owner_id=owner_id,
                result_ref=f"business_autonomy:{key}",
                metadata_patch={"business_autonomy_result": _serialize_result(payload)},
            )

    @staticmethod
    def _idem_key(raw_key: str):
        return build_idempotency_key(
            tenant_id="global",
            namespace="business_autonomy",
            operation="execute",
            key=str(raw_key),
            semantic_scope={"business_autonomy_key": str(raw_key)},
        )


class PersistentBusinessAutonomyEvidenceStore:
    def __init__(self, backend: SqliteEvidenceStore | None = None) -> None:
        self._backend = backend or SqliteEvidenceStore(SqliteSessionFactory(business_autonomy_evidence_store_path()))

    def append_result(self, result: BusinessExecutionResult) -> EvidenceRecord:
        created_at = datetime.now(UTC)
        payload = {
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
        }
        record = EvidenceRecord(
            evidence_id=str(uuid4()),
            tenant_id=str(result.metadata.get("tenant_id") or result.business_id or "global"),
            scope="business_autonomy",
            run_id=str(result.execution_id),
            action_id=str(result.goal_id),
            action_type="business_autonomy_execution",
            verification_status=result.verdict.value,
            created_at=created_at,
            refs=tuple(filter(None, (result.adapter_name, result.business_id, result.goal_id))),
            payload=payload,
            labels={
                "business_id": result.business_id,
                "goal_id": result.goal_id,
                "verdict": result.verdict.value,
            },
        )
        return self._backend.append(record)

    def list_recent(self, *, tenant_id: str, limit: int = 20) -> tuple[EvidenceRecord, ...]:
        return self._backend.list_for_tenant(tenant_id=tenant_id, limit=limit)


def _serialize_result(result: BusinessExecutionResult) -> dict[str, Any]:
    return {
        "verdict": result.verdict.value,
        "business_id": result.business_id,
        "goal_id": result.goal_id,
        "execution_id": result.execution_id,
        "message": result.message,
        "metrics": dict(result.metrics),
        "evidence": [
            {
                "event_type": item.event_type,
                "payload": dict(item.payload),
                "timestamp_utc": item.timestamp_utc,
                "source": item.source,
            }
            for item in result.evidence
        ],
        "delegated_to_domain_engine": bool(result.delegated_to_domain_engine),
        "adapter_name": result.adapter_name,
        "metadata": dict(result.metadata),
    }


def _deserialize_result(payload: Mapping[str, Any]) -> BusinessExecutionResult:
    return BusinessExecutionResult(
        verdict=ExecutionVerdict(str(payload.get("verdict") or ExecutionVerdict.REJECTED.value)),
        business_id=str(payload.get("business_id") or ""),
        goal_id=str(payload.get("goal_id") or ""),
        execution_id=str(payload.get("execution_id") or ""),
        message=str(payload.get("message") or ""),
        metrics=dict(payload.get("metrics") or {}),
        evidence=tuple(
            BusinessExecutionEvidence(
                event_type=str(item.get("event_type") or ""),
                payload=dict(item.get("payload") or {}),
                timestamp_utc=str(item.get("timestamp_utc") or ""),
                source=str(item.get("source") or ""),
            )
            for item in (payload.get("evidence") or [])
        ),
        delegated_to_domain_engine=bool(payload.get("delegated_to_domain_engine", False)),
        adapter_name=None if payload.get("adapter_name") in (None, "") else str(payload.get("adapter_name")),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "BUSINESS_AUTONOMY_OWNER_ID",
    "PersistentBusinessAutonomyAudit",
    "PersistentBusinessAutonomyEvidenceStore",
    "PersistentBusinessAutonomyIdempotencyStore",
    "PersistentAuditRecord",
    "business_autonomy_evidence_store_path",
    "business_autonomy_idempotency_store_path",
    "business_autonomy_runtime_dir",
    "PersistentBusinessApprovalGate",
    "PersistentBusinessOperatorOverridePolicy",
    "PersistentBusinessCapabilityRegistry",
    "PersistentBusinessTrustRegistry",
    "PersistentBusinessPlanningMemorySink",
    "business_autonomy_capability_registry_path",
    "business_autonomy_trust_registry_path",
]



def business_autonomy_capability_registry_path() -> Path:
    return business_autonomy_runtime_dir() / "business_autonomy_capabilities.json"


def business_autonomy_trust_registry_path() -> Path:
    return business_autonomy_runtime_dir() / "business_autonomy_trust.json"


class PersistentBusinessCapabilityRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path is not None else business_autonomy_capability_registry_path()
        self._items: dict[str, list[BusinessCapability]] = {}
        self._load()

    def register(self, business_id: str, capabilities: Sequence[BusinessCapability]) -> None:
        self._items[str(business_id)] = [
            BusinessCapability(
                kind=item.kind,
                enabled=bool(item.enabled),
                confidence=float(item.confidence),
                notes=item.notes,
            )
            for item in capabilities
        ]
        self._flush()

    def get(self, business_id: str):
        key = str(business_id)
        if key not in self._items:
            raise KeyError(f"Capabilities not registered for business_id={key}")
        from application.business_autonomy.registry import RegisteredBusinessCapabilities
        return RegisteredBusinessCapabilities(business_id=key, capabilities=tuple(self._items[key]))

    def supports(self, business_id: str, kind: CapabilityKind) -> bool:
        try:
            entry = self.get(business_id)
        except KeyError:
            return False
        return any(item.kind == kind and item.enabled for item in entry.capabilities)

    def snapshot(self):
        from application.business_autonomy.registry import RegisteredBusinessCapabilities
        return {
            key: RegisteredBusinessCapabilities(business_id=key, capabilities=tuple(value))
            for key, value in self._items.items()
        }

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"items": {}})
        items = raw.get("items", {}) if isinstance(raw, dict) else {}
        loaded: dict[str, list[BusinessCapability]] = {}
        for business_id, caps in items.items():
            loaded[str(business_id)] = [
                BusinessCapability(
                    kind=CapabilityKind(str(item.get("kind"))),
                    enabled=bool(item.get("enabled", True)),
                    confidence=float(item.get("confidence", 1.0)),
                    notes=item.get("notes"),
                )
                for item in caps or []
            ]
        self._items = loaded

    def _flush(self) -> None:
        atomic_write_json(
            self._path,
            {
                "items": {
                    key: [
                        {
                            "kind": item.kind.value,
                            "enabled": item.enabled,
                            "confidence": item.confidence,
                            "notes": item.notes,
                        }
                        for item in values
                    ]
                    for key, values in self._items.items()
                }
            },
        )


class PersistentBusinessTrustRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path is not None else business_autonomy_trust_registry_path()
        self._items: dict[str, BusinessTrustSnapshot] = {}
        self._load()

    def register(self, snapshot: BusinessTrustSnapshot) -> None:
        self._items[str(snapshot.business_id)] = snapshot
        self._flush()

    def get(self, business_id: str) -> BusinessTrustSnapshot:
        key = str(business_id)
        return self._items.get(
            key,
            BusinessTrustSnapshot(
                business_id=key,
                trust_tier=BusinessTrustTier.UNKNOWN,
                score=0.0,
                reasons=("No trust profile registered.",),
                metadata={},
            ),
        )

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"items": {}})
        items = raw.get("items", {}) if isinstance(raw, dict) else {}
        loaded: dict[str, BusinessTrustSnapshot] = {}
        for business_id, payload in items.items():
            loaded[str(business_id)] = BusinessTrustSnapshot(
                business_id=str(business_id),
                trust_tier=BusinessTrustTier(str(payload.get("trust_tier", BusinessTrustTier.UNKNOWN.value))),
                score=float(payload.get("score", 0.0)),
                reasons=tuple(str(x) for x in payload.get("reasons", []) if str(x).strip()),
                metadata=dict(payload.get("metadata") or {}),
            )
        self._items = loaded

    def _flush(self) -> None:
        atomic_write_json(
            self._path,
            {
                "items": {
                    key: {
                        "trust_tier": value.trust_tier.value,
                        "score": value.score,
                        "reasons": list(value.reasons),
                        "metadata": dict(value.metadata or {}),
                    }
                    for key, value in self._items.items()
                }
            },
        )


class PersistentBusinessApprovalGate:
    def __init__(self, store=None) -> None:
        self._store = store or build_default_approval_store()

    def evaluate(self, *, request, requires_approval: bool):
        from application.business_autonomy.guards import ApprovalDecision as GateDecision
        from application.business_autonomy.guards import ApprovalStatus as GateStatus

        explicit_constraint_requires_approval = any(
            item.name == "require_human_approval" and bool(item.value) is True
            for item in request.envelope.constraints
        )
        if not requires_approval and not explicit_constraint_requires_approval:
            return GateDecision(GateStatus.NOT_REQUIRED, "Approval is not required.")

        metadata = dict(request.envelope.metadata)
        tenant_id = str(metadata.get("tenant_id") or "").strip()
        if not tenant_id or tenant_id == "global":
            return GateDecision(GateStatus.REJECTED, "Canonical approval requires an explicit tenant.")
        approval_id = str(metadata.get("approval_id") or f"business-autonomy:{request.envelope.business_id}:{request.envelope.goal_id}")
        existing = self._store.get(approval_id)
        if existing is None:
            approval_request = ApprovalRequest(
                approval_id=approval_id,
                tenant_id=tenant_id,
                subject_type="business_autonomy_execution",
                subject_id=str(request.envelope.goal_id),
                requested_by=str(request.envelope.requested_by or "platform"),
                reason=str(metadata.get("approval_reason") or "Business autonomy execution requires approval."),
                metadata={
                    "business_id": request.envelope.business_id,
                    "goal_id": request.envelope.goal_id,
                    "goal_type": request.envelope.goal_type,
                },
            )
            try:
                existing = self._store.create(approval_request)
            except ValueError:
                existing = self._store.get(approval_id)

        if existing is None:
            return GateDecision(GateStatus.PENDING, "Approval request could not be resolved.")
        bound_business_id = str(existing.request.metadata.get("business_id") or "")
        if (
            existing.request.tenant_id != tenant_id
            or existing.request.subject_type != "business_autonomy_execution"
            or existing.request.subject_id != str(request.envelope.goal_id)
            or bound_business_id != str(request.envelope.business_id)
        ):
            return GateDecision(GateStatus.REJECTED, "Approval binding mismatch.")
        if existing.status is ApprovalStatus.APPROVED:
            approver = existing.decisions[-1].actor_id if existing.decisions else ""
            return GateDecision(GateStatus.APPROVED, "Approval provided by canonical governance.", str(approver))
        if existing.status in {ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED, ApprovalStatus.EXPIRED}:
            return GateDecision(GateStatus.REJECTED, f"Approval not granted: {existing.status.value}.")
        return GateDecision(GateStatus.PENDING, "Approval required but not yet provided.")


class PersistentBusinessOperatorOverridePolicy:
    def __init__(self, store=None) -> None:
        self._store = store or build_default_operator_override_store()

    def evaluate(self, request):
        from application.business_autonomy.guards import OperatorOverrideDecision as GateDecision
        from application.business_autonomy.guards import OperatorOverrideMode

        override_id = dict(request.envelope.metadata).get("override_id")
        if not override_id:
            return GateDecision(OperatorOverrideMode.NONE, "No canonical operator override is recorded.")
        record = self._store.get(str(override_id))
        if record is None or record.status is not OperatorOverrideStatus.APPROVED or record.decision is None:
            return GateDecision(OperatorOverrideMode.NONE, "Canonical operator override is not approved.")
        try:
            record.validate_binding(**_operator_override_binding(request))
        except (RuntimeError, ValueError) as exc:
            return GateDecision(OperatorOverrideMode.FORCE_DENY, str(exc), override_id=str(override_id))
        mode = {
            OperatorOverrideResolution.APPROVE_ONCE: OperatorOverrideMode.FORCE_ALLOW,
            OperatorOverrideResolution.REJECT: OperatorOverrideMode.FORCE_DENY,
            OperatorOverrideResolution.RETRY: OperatorOverrideMode.FORCE_ALLOW,
            OperatorOverrideResolution.DOWNGRADE_TO_SUPERVISED: OperatorOverrideMode.FORCE_SIMULATION,
            OperatorOverrideResolution.CANCEL: OperatorOverrideMode.FORCE_DENY,
        }.get(record.decision.resolution, OperatorOverrideMode.NONE)
        return GateDecision(
            mode=mode,
            reason=str(record.decision.note),
            operator_id=str(record.decision.actor_id),
            override_id=str(override_id),
        )

    def consume(self, *, override_id: str, request) -> None:
        record = self._store.get(str(override_id))
        if record is None or record.status is not OperatorOverrideStatus.APPROVED or record.decision is None:
            raise RuntimeError("canonical_operator_override_not_approved")
        record.validate_binding(**_operator_override_binding(request))
        if record.decision.resolution is OperatorOverrideResolution.APPROVE_ONCE:
            updated = record.consume_once(execution_id=str(request.correlation_id))
        elif record.decision.resolution is OperatorOverrideResolution.RETRY:
            updated = replace(
                record,
                status=OperatorOverrideStatus.CONSUMED,
                consumed_at=datetime.now(UTC),
                consumed_by_execution_id=str(request.correlation_id),
                final_reason="retry_override_consumed",
            )
        else:
            return
        self._store.save(updated)


def _operator_override_binding(request) -> dict[str, str]:
    from execution.operator_override_contract import build_operator_override_subject_fingerprint

    metadata = dict(request.envelope.metadata)
    tenant_id = str(metadata.get("tenant_id") or "").strip()
    execution_id = str(request.correlation_id)
    decision_id = str(metadata.get("decision_id") or request.envelope.goal_id)
    action_name = str(metadata.get("action_type") or request.envelope.goal_type)
    subject_fingerprint = build_operator_override_subject_fingerprint(
        tenant_id=tenant_id,
        execution_id=execution_id,
        decision_id=decision_id,
        action_name=action_name,
        subject_payload=dict(request.envelope.goal_payload),
    )
    return {
        "tenant_id": tenant_id,
        "execution_id": execution_id,
        "decision_id": decision_id,
        "action_name": action_name,
        "subject_fingerprint": subject_fingerprint,
    }


class PersistentBusinessPlanningMemorySink:
    def __init__(self, goal_plan_store: FileGoalPlanMemoryStore | None = None, strategy_store: FileStrategyMemoryStore | None = None, multi_goal_store: FileMultiGoalPlannerStore | None = None) -> None:
        root = business_autonomy_runtime_dir() / "planning_memory"
        self._goal_plan = GoalPlanMemoryService(store=goal_plan_store or FileGoalPlanMemoryStore(root_dir=root / "goal_plans"))
        self._strategy = StrategyMemoryService(store=strategy_store or FileStrategyMemoryStore(root_dir=root / "strategy"))
        self._long_horizon = LongHorizonPlanner(strategy_memory=self._strategy)
        self._multi_goal = MultiGoalPlannerService(
            store=multi_goal_store or FileMultiGoalPlannerStore(root_dir=root / "multi_goal"),
            long_horizon_planner=self._long_horizon,
        )

    def record_execution(self, *, request: BusinessGoalEnvelope, result: BusinessExecutionResult) -> None:
        tenant_id = str(request.metadata.get("tenant_id") or result.metadata.get("tenant_id") or request.business_id or "global")
        business_id = str(request.business_id)
        goal = str(request.goal_id or request.goal_type)
        goal_family = str(request.metadata.get("goal_family") or request.goal_type or "default")
        plan_context = {
            "planning_horizon": request.metadata.get("planning_horizon", "week"),
            "tasks": tuple(),
        }
        feedback = {
            "verified": result.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED},
            "verification_status": result.verdict.value,
            "goal_reached": result.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED},
            "updated_at": datetime.now(UTC).isoformat(),
            "approval_required": any(c.name == "require_human_approval" and bool(c.value) for c in request.constraints),
            "blocked_by_policy": result.verdict is ExecutionVerdict.REJECTED,
            "performance_feedback_learning": {
                "preferred_planning_horizon": request.metadata.get("planning_horizon", "week"),
                "cost_efficiency_score": float(result.metrics.get("cost_efficiency_score", 1.0 if result.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED} else 0.0)),
            },
            "goal_evaluation": {
                "achieved": result.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED},
                "completion_ratio": 1.0 if result.verdict in {ExecutionVerdict.COMPLETED, ExecutionVerdict.SIMULATED} else 0.0,
            },
        }
        self._goal_plan.update_after_step(
            tenant_id=tenant_id,
            business_id=business_id,
            goal=goal,
            step_index=0,
            action_type=request.goal_type,
            feedback=feedback,
        )
        self._strategy.update_after_feedback(
            tenant_id=tenant_id,
            business_id=business_id,
            goal_family=goal_family,
            plan_context=plan_context,
            feedback=feedback,
        )
        queue_snapshot = self._multi_goal.load_context(tenant_id=tenant_id, business_id=business_id)
        goals = tuple(queue_snapshot.get("goals") or ())
        if not any(str(item.get("goal_id") or "") == str(request.goal_id) for item in goals if isinstance(item, Mapping)):
            metadata = dict(request.metadata)
            metadata.setdefault("goal_family", goal_family)
            metadata.setdefault("business_autonomy", True)
            self._multi_goal.add_goal(
                tenant_id=tenant_id,
                business_id=business_id,
                goal_id=str(request.goal_id),
                goal=str(request.goal_type),
                metadata=metadata,
                priority=int(request.priority),
                urgency=int(request.priority),
                budget_weight=1.0,
            )
        plan_view = self._long_horizon.build_plan(
            tenant_id=tenant_id,
            business_id=business_id,
            goal=str(request.goal_type),
            metadata={"goal_family": goal_family, "planning_horizon": request.metadata.get("planning_horizon", "week")},
        )
        self._strategy.update_after_feedback(
            tenant_id=tenant_id,
            business_id=business_id,
            goal_family=goal_family,
            plan_context=plan_view.to_dict(),
            feedback={"strategic_signal": "business_autonomy_execution", **feedback},
        )
