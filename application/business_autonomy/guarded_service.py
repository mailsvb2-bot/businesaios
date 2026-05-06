from __future__ import annotations

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult, ExecutionVerdict
from application.business_autonomy.guards import (
    ApprovalStatus,
    BusinessApprovalGate,
    BusinessBlastRadiusGuard,
    BusinessBudgetGuard,
    BusinessIdempotencyStore,
    BusinessOperatorOverridePolicy,
    OperatorOverrideMode,
)
from application.business_autonomy.policy import BusinessTrustPolicy
from application.business_autonomy.policy_alignment import BusinessAutonomyCapabilityVerdictBridge
from application.business_autonomy.service import BusinessAutonomyService


class BusinessAutonomyGuardedService:
    def __init__(
        self,
        *,
        autonomy_service: BusinessAutonomyService,
        trust_policy: BusinessTrustPolicy,
        budget_guard: BusinessBudgetGuard,
        blast_radius_guard: BusinessBlastRadiusGuard,
        approval_gate: BusinessApprovalGate,
        idempotency_store: BusinessIdempotencyStore,
        operator_override_policy: BusinessOperatorOverridePolicy,
        audit_sink: object | None = None,
        evidence_store: object | None = None,
        planning_memory_sink: object | None = None,
        governance_alignment_bridge: BusinessAutonomyCapabilityVerdictBridge | None = None,
    ) -> None:
        self._autonomy_service = autonomy_service
        self._trust_policy = trust_policy
        self._budget_guard = budget_guard
        self._blast_radius_guard = blast_radius_guard
        self._approval_gate = approval_gate
        self._idempotency_store = idempotency_store
        self._operator_override_policy = operator_override_policy
        self._audit_sink = audit_sink
        self._evidence_store = evidence_store
        self._planning_memory_sink = planning_memory_sink
        self._governance_alignment_bridge = governance_alignment_bridge or BusinessAutonomyCapabilityVerdictBridge()

    async def execute(self, request: BusinessExecutionRequest) -> BusinessExecutionResult:
        scoped_idempotency_key = _scoped_idempotency_key(request)
        cached = self._idempotency_store.get(scoped_idempotency_key)
        if cached is not None:
            return cached

        override = self._operator_override_policy.evaluate(request)
        if override.mode == OperatorOverrideMode.FORCE_DENY:
            result = BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=request.envelope.business_id,
                goal_id=request.envelope.goal_id,
                execution_id=request.correlation_id,
                message=f"Execution denied by operator override: {override.reason}",
                metadata={"operator_override_mode": override.mode.value},
            )
            _cache_terminal_result(self._idempotency_store, scoped_idempotency_key, result)
            return result

        effective_request = request
        if override.mode == OperatorOverrideMode.FORCE_SIMULATION:
            effective_request = BusinessExecutionRequest(
                envelope=type(request.envelope)(
                    business_id=request.envelope.business_id,
                    goal_id=request.envelope.goal_id,
                    goal_type=request.envelope.goal_type,
                    goal_payload=request.envelope.goal_payload,
                    priority=request.envelope.priority,
                    requested_by=request.envelope.requested_by,
                    simulation=True,
                    constraints=request.envelope.constraints,
                    metadata=request.envelope.metadata,
                ),
                integration_mode=request.integration_mode,
                correlation_id=request.correlation_id,
                idempotency_key=request.idempotency_key,
                timeout_seconds=request.timeout_seconds,
            )

        budget = self._budget_guard.evaluate(effective_request)
        if not budget.allowed and override.mode != OperatorOverrideMode.FORCE_ALLOW:
            result = BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message=budget.reason,
                metadata={"budget_limit": budget.budget_limit, "estimated_cost": budget.estimated_cost},
            )
            _cache_terminal_result(self._idempotency_store, scoped_idempotency_key, result)
            return result

        blast = self._blast_radius_guard.evaluate(effective_request)
        if not blast.allowed and override.mode != OperatorOverrideMode.FORCE_ALLOW:
            result = BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message=blast.reason,
                metadata={"outbound_limit": blast.outbound_limit, "requested_outbound": blast.requested_outbound},
            )
            _cache_terminal_result(self._idempotency_store, scoped_idempotency_key, result)
            return result

        trust = self._trust_policy.evaluate(effective_request)
        governance_alignment = self._governance_alignment_bridge.build_alignment(
            request=effective_request,
            capability_allowed=trust.allowed,
            policy_verdict={
                "allowed": trust.allowed,
                "reason": trust.reason,
                "operator_required": trust.requires_approval,
                "recommended_autonomy_tier": effective_request.envelope.metadata.get("autonomy_tier", "bounded_autonomy"),
            },
        )
        if not trust.allowed and override.mode != OperatorOverrideMode.FORCE_ALLOW:
            result = BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message=trust.reason,
                metadata={"trust_reason": trust.reason, "capability_execution_verdict": dict(governance_alignment.execution_verdict)},
            )
            _cache_terminal_result(self._idempotency_store, scoped_idempotency_key, result)
            return result

        approval = self._approval_gate.evaluate(request=effective_request, requires_approval=trust.requires_approval)
        if approval.status == ApprovalStatus.PENDING and override.mode != OperatorOverrideMode.FORCE_ALLOW:
            result = BusinessExecutionResult(
                verdict=ExecutionVerdict.PARTIAL,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message=approval.reason,
                metadata={"approval_status": approval.status.value, "capability_execution_verdict": dict(governance_alignment.execution_verdict)},
            )
            return result

        result = await self._autonomy_service.execute(effective_request)
        result = type(result)(
            verdict=result.verdict,
            business_id=result.business_id,
            goal_id=result.goal_id,
            execution_id=result.execution_id,
            message=result.message,
            metrics=result.metrics,
            evidence=result.evidence,
            delegated_to_domain_engine=result.delegated_to_domain_engine,
            adapter_name=result.adapter_name,
            metadata={**dict(result.metadata), "capability_execution_verdict": dict(governance_alignment.execution_verdict)},
        )
        _cache_terminal_result(self._idempotency_store, scoped_idempotency_key, result)
        if self._evidence_store is not None and hasattr(self._evidence_store, "append_result"):
            self._evidence_store.append_result(result)
        if self._planning_memory_sink is not None and hasattr(self._planning_memory_sink, "record_execution"):
            self._planning_memory_sink.record_execution(request=effective_request.envelope, result=result)
        if self._audit_sink is not None and hasattr(self._audit_sink, "record"):
            self._audit_sink.record(
                event_type="business_autonomy_guarded_result",
                business_id=result.business_id,
                goal_id=result.goal_id,
                detail={"verdict": result.verdict.value, "delegated": result.delegated_to_domain_engine},
            )
        return result


def _cache_terminal_result(idempotency_store: BusinessIdempotencyStore, key: str, result: BusinessExecutionResult) -> None:
    if result.verdict in {
        ExecutionVerdict.COMPLETED,
        ExecutionVerdict.SIMULATED,
        ExecutionVerdict.REJECTED,
        ExecutionVerdict.FAILED,
    }:
        idempotency_store.put(key, result)


def _scoped_idempotency_key(request: BusinessExecutionRequest) -> str:
    tenant_id = str(request.envelope.metadata.get("tenant_id") or "global").strip() or "global"
    business_id = str(request.envelope.business_id or "unknown").strip() or "unknown"
    raw_key = str(request.idempotency_key or request.correlation_id).strip() or str(request.correlation_id)
    return f"{tenant_id}:{business_id}:{raw_key}"


def _read_document_state(path):
    """Read a versioned business-autonomy document state."""
    import json
    from pathlib import Path

    target = Path(path)
    if not target.exists():
        return {"version": 0, "items": {}}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("business_autonomy_distributed_state_corrupt") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("business_autonomy_distributed_state_invalid")
    version = int(payload.get("version") or 0)
    items = payload.get("items") or {}
    if not isinstance(items, dict):
        raise RuntimeError("business_autonomy_distributed_state_items_invalid")
    return {"version": version, "items": items}


def _write_document_state(path, items, *, expected_version: int):
    """Atomically write a versioned state document with fail-closed CAS."""
    import json
    import os
    from pathlib import Path

    target = Path(path)
    state = _read_document_state(target)
    if int(state["version"]) != int(expected_version):
        raise RuntimeError("business_autonomy_distributed_state_version_conflict")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = {"version": int(expected_version) + 1, "items": dict(items or {})}
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, target)
    return payload
