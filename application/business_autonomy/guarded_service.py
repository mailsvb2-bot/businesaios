from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timezone
from pathlib import Path

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
        business_id: str | None = None,
        *,
        autonomy_service: BusinessAutonomyService | None = None,
        trust_policy: BusinessTrustPolicy | None = None,
        budget_guard: BusinessBudgetGuard | None = None,
        blast_radius_guard: BusinessBlastRadiusGuard | None = None,
        approval_gate: BusinessApprovalGate | None = None,
        idempotency_store: BusinessIdempotencyStore | None = None,
        operator_override_policy: BusinessOperatorOverridePolicy | None = None,
        audit_sink: object | None = None,
        evidence_store: object | None = None,
        planning_memory_sink: object | None = None,
        governance_alignment_bridge: BusinessAutonomyCapabilityVerdictBridge | None = None,
    ) -> None:
        self.business_id = str(business_id or '').strip()
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
        if self._autonomy_service is None or self._trust_policy is None or self._budget_guard is None or self._blast_radius_guard is None or self._approval_gate is None or self._idempotency_store is None or self._operator_override_policy is None:
            return BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=request.envelope.business_id,
                goal_id=request.envelope.goal_id,
                execution_id=request.correlation_id,
                message='business autonomy guarded execution dependencies are not configured',
                metadata={'surface': 'compatibility_guarded_service'},
            )
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
        budget_safety = dict(budget.safety_verdict or {"allowed": bool(budget.allowed), "reason": "legacy_budget_guard", "source": "legacy"})
        if not budget.allowed and override.mode != OperatorOverrideMode.FORCE_ALLOW:
            result = BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message=budget.reason,
                metadata={
                    "budget_limit": budget.budget_limit,
                    "estimated_cost": budget.estimated_cost,
                    "safety_core": {"budget": budget_safety},
                },
            )
            _cache_terminal_result(self._idempotency_store, scoped_idempotency_key, result)
            return result

        blast = self._blast_radius_guard.evaluate(effective_request)
        blast_safety = dict(blast.safety_verdict or {"allowed": bool(blast.allowed), "reason": "legacy_blast_radius_guard", "source": "legacy"})
        if not blast.allowed and override.mode != OperatorOverrideMode.FORCE_ALLOW:
            result = BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message=blast.reason,
                metadata={
                    "outbound_limit": blast.outbound_limit,
                    "requested_outbound": blast.requested_outbound,
                    "safety_core": {"budget": budget_safety, "blast_radius": blast_safety},
                },
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
                metadata={
                    "trust_reason": trust.reason,
                    "capability_execution_verdict": dict(governance_alignment.execution_verdict),
                    "safety_core": {"budget": budget_safety, "blast_radius": blast_safety},
                },
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
                metadata={
                    "approval_status": approval.status.value,
                    "capability_execution_verdict": dict(governance_alignment.execution_verdict),
                    "safety_core": {"budget": budget_safety, "blast_radius": blast_safety},
                },
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
            metadata={
                **dict(result.metadata),
                "capability_execution_verdict": dict(governance_alignment.execution_verdict),
                "safety_core": {"budget": budget_safety, "blast_radius": blast_safety},
            },
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
                detail={
                    "verdict": result.verdict.value,
                    "delegated": result.delegated_to_domain_engine,
                    "safety_core": {"budget": budget_safety, "blast_radius": blast_safety},
                },
            )
        return result

    def _record_distributed_state_conflict(self, *, tenant_id: str, business_id: str, document: str, expected_version: int | None = None, current_version: int | None = None, recovery_plan: str = 'reload_merge_retry') -> None:
        append_dir = _distributed_append_dir()
        append_dir.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        event = {
            'event': 'business_autonomy_distributed_state_version_conflict',
            'tenant_id': tenant_id,
            'business_id': business_id,
            'document': document,
            'expected_version': expected_version,
            'current_version': current_version,
            'recovery_plan': recovery_plan,
            'recorded_at_utc': now,
        }
        with (append_dir / 'distributed_state_conflicts.jsonl').open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(event, sort_keys=True) + '\n')
        state_path = append_dir / 'distributed_state_conflicts_state.json'
        state = _read_plain_state(state_path)
        key = _conflict_key(tenant_id=tenant_id, business_id=business_id, document=document)
        previous = dict(state.get('items', {}).get(key) or {})
        occurrence_count = int(previous.get('occurrence_count') or 0) + 1
        row = {
            **previous,
            'tenant_id': tenant_id,
            'business_id': business_id,
            'document': document,
            'status': 'open',
            'expected_version': expected_version,
            'current_version': current_version,
            'recovery_plan': recovery_plan,
            'occurrence_count': occurrence_count,
            'first_recorded_at_utc': previous.get('first_recorded_at_utc') or now,
            'last_recorded_at_utc': now,
            'acknowledged_by': '',
            'acknowledged_at_utc': '',
            'resolved_by': '',
            'resolution_note': '',
            'resolved_at_utc': '',
        }
        _write_plain_state(state_path, {**dict(state.get('items') or {}), key: row})

    def acknowledge_distributed_state_conflict(self, *, tenant_id: str, business_id: str, document: str, acknowledged_by: str) -> bool:
        return _update_conflict_state(
            tenant_id=tenant_id,
            business_id=business_id,
            document=document,
            updates={'status': 'acknowledged', 'acknowledged_by': acknowledged_by, 'acknowledged_at_utc': _utc_now()},
        )

    def resolve_distributed_state_conflict(self, *, tenant_id: str, business_id: str, document: str, resolved_by: str, resolution_note: str) -> bool:
        return _update_conflict_state(
            tenant_id=tenant_id,
            business_id=business_id,
            document=document,
            updates={'status': 'resolved', 'resolved_by': resolved_by, 'resolution_note': resolution_note, 'resolved_at_utc': _utc_now()},
        )


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


def _distributed_append_dir() -> Path:
    return Path(os.environ.get('DATA_DIR', 'data')) / 'runtime' / 'distributed' / 'append'


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _conflict_key(*, tenant_id: str, business_id: str, document: str) -> str:
    return f'{tenant_id}:{business_id}:{document}'


def _read_plain_state(path: Path) -> dict:
    if not path.exists():
        return {'items': {}}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'items': {}}
    if isinstance(payload, dict) and 'items' in payload and isinstance(payload['items'], dict):
        return payload
    if isinstance(payload, dict):
        return {'items': payload}
    return {'items': {}}


def _write_plain_state(path: Path, items: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'items': items}, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def _update_conflict_state(*, tenant_id: str, business_id: str, document: str, updates: dict) -> bool:
    path = _distributed_append_dir() / 'distributed_state_conflicts_state.json'
    state = _read_plain_state(path)
    key = _conflict_key(tenant_id=tenant_id, business_id=business_id, document=document)
    row = dict(state.get('items', {}).get(key) or {})
    if not row:
        return False
    row.update(updates)
    _write_plain_state(path, {**dict(state.get('items') or {}), key: row})
    return True


def _read_document_state(path):
    """Read a versioned business-autonomy document state."""
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
