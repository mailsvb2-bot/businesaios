from __future__ import annotations

from contextlib import suppress
from typing import Any

from bootstrap.safety_control_boot import build_safety_control_runtime
from core.safety.controls.action_identity import canonical_action_id, canonical_breaker_key
from core.safety.controls.observability.event_store import SafetyEvent
from runtime.safety import ControlDecision, ControlStatus, SafetyActionContext


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload or {})




def _worker_owner(payload: Any) -> str:
    data = _payload_dict(payload)
    return str(data.get("worker_id") or data.get("executor_id") or data.get("runtime_owner") or '').strip()

def build_runtime_safety_context(*, action: str, payload: Any) -> SafetyActionContext:
    data = _payload_dict(payload)
    tenant_id = str(data.get("tenant_id") or "unknown")
    return SafetyActionContext(
        action=str(action),
        tenant_id=tenant_id,
        user_id=str(data.get("user_id")) if data.get("user_id") is not None else None,
        payload=data,
        metadata={
            "action_id": canonical_action_id(action=str(action), tenant_id=tenant_id, payload=data),
        },
    )


def _record_safety_event(*, action: str, payload: Any, stage: str, status: str, control: str = '', reason: str = '', details: dict[str, Any] | None = None) -> None:
    runtime = build_safety_control_runtime()
    data = _payload_dict(payload)
    try:
        runtime.profile.event_store.append(
            SafetyEvent(
                tenant_id=str(data.get('tenant_id') or 'unknown'),
                action=str(action),
                stage=str(stage),
                status=str(status),
                control=str(control),
                reason=str(reason),
                details=dict(details or {}),
            )
        )
    except Exception:
        return


def evaluate_runtime_action_controls(*, action: str, payload: Any) -> list[ControlDecision]:
    ctx = build_runtime_safety_context(action=action, payload=payload)
    runtime = build_safety_control_runtime()
    decisions = runtime.action_controls_for_tenant(ctx.tenant_id).evaluate(ctx)
    for decision in decisions:
        _record_safety_event(
            action=action,
            payload=payload,
            stage='evaluate',
            status=str(decision.status.value if hasattr(decision.status, 'value') else decision.status),
            control=decision.control,
            reason=decision.reason,
            details=dict(decision.details),
        )
    return decisions


def record_allowed_action(*, action: str, payload: Any) -> None:
    runtime = build_safety_control_runtime()
    data = _payload_dict(payload)
    spec = runtime.profile.action_catalog.resolve(str(action))
    default_cost = float(getattr(spec, "default_estimated_cost", 0.0) or 0.0)
    estimated_cost = float(data.get("estimated_cost", default_cost) or default_cost)
    runtime.profile.action_budget_ledger.record(str(data.get("tenant_id") or "unknown"), estimated_cost=estimated_cost)
    _record_safety_event(action=action, payload=payload, stage='allow', status='allow', reason='budget_recorded', details={'estimated_cost': estimated_cost})


def record_action_success(*, action: str, payload: Any) -> None:
    runtime = build_safety_control_runtime()
    data = _payload_dict(payload)
    tenant_id = str(data.get("tenant_id") or "unknown")
    runtime.profile.circuit_breaker_feedback.record_success(
        canonical_breaker_key(action=str(action), tenant_id=tenant_id)
    )
    action_id = canonical_action_id(action=str(action), tenant_id=tenant_id, payload=data)
    with suppress(Exception):
        runtime.profile.rollback_planner.mark_executed(tenant_id=tenant_id, action_id=action_id)
    owner = _worker_owner(payload)
    try:
        if owner and hasattr(runtime.profile.approval_repository, 'acquire_lease'):
            runtime.profile.approval_repository.acquire_lease(action_id=action_id, owner=owner)
        runtime.profile.approval_repository.mark_executed(action_id=action_id)
    except Exception:
        pass

    if bool(data.get('rollback_verification_required')) or str(action).startswith('rollback_'):
        try:
            verification = runtime.profile.rollback_verifier.verify(
                expected_state=dict(data.get('rollback_expected_state') or {}),
                observed_state=dict(data.get('rollback_observed_state') or {}),
            )
            runtime.profile.rollback_planner.reconcile(tenant_id=tenant_id, action_id=action_id, expected_state=dict(data.get('rollback_expected_state') or {}), observed_state=dict(data.get('rollback_observed_state') or {}))
            _record_safety_event(action=action, payload=payload, stage='rollback_verify', status='success', reason='rollback_verified', details={'checked_keys': list(verification.checked_keys)})
        except Exception as exc:
            runtime.profile.rollback_planner.reconcile(tenant_id=tenant_id, action_id=action_id, expected_state=dict(data.get('rollback_expected_state') or {}), observed_state=dict(data.get('rollback_observed_state') or {}))
            _record_safety_event(action=action, payload=payload, stage='rollback_verify', status='failure', reason='rollback_verification_failed', details={'error': str(exc)})
    _record_safety_event(action=action, payload=payload, stage='outcome', status='success', reason='execution_succeeded')


def record_action_failure(*, action: str, payload: Any) -> None:
    runtime = build_safety_control_runtime()
    data = _payload_dict(payload)
    tenant_id = str(data.get("tenant_id") or "unknown")
    runtime.profile.circuit_breaker_feedback.record_failure(
        canonical_breaker_key(action=str(action), tenant_id=tenant_id)
    )
    ctx = build_runtime_safety_context(action=action, payload=payload)
    try:
        plan = runtime.profile.rollback_planner.build(ctx)
        action_id = canonical_action_id(action=str(action), tenant_id=tenant_id, payload=data)
        owner = _worker_owner(payload)
        if owner and hasattr(runtime.profile.rollback_planner._store, 'acquire_lease'):
            runtime.profile.rollback_planner._store.acquire_lease(tenant_id=tenant_id, action_id=action_id, owner=owner)
        runtime.profile.rollback_planner.confirm_execution(tenant_id=tenant_id, action_id=action_id, confirmation_token=plan.confirmation_token)
        runtime.profile.rollback_planner.append_receipt(tenant_id=tenant_id, action_id=action_id, step_index=0, action='rollback_prepare', status='confirmed', details={'source_action': str(action), 'worker_owner': owner})
    except Exception:
        pass
    _record_safety_event(action=action, payload=payload, stage='outcome', status='failure', reason='execution_failed')


def record_execution_outcome(*, action: str, payload: Any, success: bool) -> None:
    if success:
        record_action_success(action=action, payload=payload)
    else:
        record_action_failure(action=action, payload=payload)


def first_blocking_decision(decisions: list[ControlDecision]) -> ControlDecision | None:
    for decision in decisions:
        if decision.status in {ControlStatus.BLOCK, ControlStatus.REVIEW}:
            return decision
    return None
