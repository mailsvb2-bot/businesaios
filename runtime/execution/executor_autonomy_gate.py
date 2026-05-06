from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard
from tenancy.tenant_policy_store import ensure_tenant_policy_bundle
from tenancy.tenant_registry import ensure_tenant_record

from runtime.decision import DecisionEnvelope
from runtime.execution.executor_autonomy_policy import (
    DEFAULT_RUNTIME_AUTONOMY_GATE_POLICY,
    extract_runtime_autonomy_cost_envelope,
    has_runtime_autonomy_contract,
)


def ensure_tenant_runtime_contracts(*, executor: Any, tenant_id: str) -> None:
    tid = str(tenant_id or '').strip()
    if not tid:
        return
    registry = getattr(executor, '_tenant_registry', None)
    if registry is not None and hasattr(registry, 'register'):
        ensure_tenant_record(registry, tid)
    policy_store = (
        getattr(getattr(executor, '_tenant_runtime_isolation', None), '_policy_store', None)
        or getattr(getattr(executor, '_tenant_execution_budget_guard', None), '_policy_store', None)
        or getattr(getattr(executor, '_runtime_infra', None), 'tenant_policy_store', None)
    )
    if policy_store is not None and hasattr(policy_store, 'save') and hasattr(policy_store, 'get'):
        ensure_tenant_policy_bundle(policy_store, tid)


def tenant_runtime_context(*, executor: Any, env: DecisionEnvelope, payload: Mapping[str, Any]):
    isolation = getattr(executor, '_tenant_runtime_isolation', None)
    tenant_id = str(payload.get('tenant_id') or payload.get('tenant') or '').strip()
    if isolation is None or not tenant_id:
        return nullcontext()
    ensure_tenant_runtime_contracts(executor=executor, tenant_id=tenant_id)
    decision = getattr(env, 'decision', None)
    run_id = str(
        payload.get('run_id')
        or getattr(decision, 'decision_id', '')
        or payload.get('action_id')
        or ''
    ).strip()
    if not run_id:
        return nullcontext()
    labels = {
        'action_type': str(getattr(decision, 'action', '') or payload.get('action_type') or ''),
        'correlation_id': str(getattr(decision, 'correlation_id', '') or ''),
    }
    labels = {k: v for k, v in labels.items() if v}
    return isolation.bind_run(
        tenant_id=require_tenant_id(tenant_id),
        run_id=run_id,
        owner_id=executor._runtime_owner_id,
        labels=labels,
    )


def deny_autonomy_execution(
    *,
    executor: Any,
    env: DecisionEnvelope,
    reason: str,
    payload: Mapping[str, Any] | None = None,
) -> None:
    events = getattr(executor, '_events', None)
    safe_payload = executor._safe_dict(payload)
    if events is not None and hasattr(events, 'emit'):
        try:
            events.emit(
                event_type='runtime_autonomy_execution_denied',
                source='runtime.executor',
                user_id='system',
                decision_id=str(getattr(env.decision, 'decision_id', '')),
                correlation_id=str(getattr(env.decision, 'correlation_id', '')),
                payload={
                    'reason': str(reason),
                    'action': str(getattr(env.decision, 'action', '') or ''),
                    'tenant_id': str(safe_payload.get('tenant_id') or ''),
                    'business_id': str(safe_payload.get('business_id') or ''),
                },
            )
        except Exception as emit_exc:
            executor._logger.warning('runtime_autonomy_execution_denied_event_emit_failed', exc_info=emit_exc)
    raise RuntimeError(str(reason))


def enforce_runtime_budget_and_blast_radius(*, executor: Any, env: DecisionEnvelope):
    payload = executor._safe_dict(getattr(env.decision, 'payload', {}) or {})
    action_type = str(getattr(env.decision, 'action', '') or payload.get('action_type') or '')
    if not has_runtime_autonomy_contract(payload, policy=DEFAULT_RUNTIME_AUTONOMY_GATE_POLICY):
        return None
    decision_action = str(getattr(env.decision, 'action', '') or '')
    payload_action = str(payload.get('action_type') or '')
    if not decision_action and not payload_action:
        deny_autonomy_execution(
            executor=executor,
            env=env,
            reason='autonomy_safety_denied:missing_action_type',
            payload=payload,
        )
    if decision_action and payload_action and decision_action != payload_action:
        deny_autonomy_execution(
            executor=executor,
            env=env,
            reason='autonomy_safety_denied:action_type_mismatch',
            payload=payload,
        )
    tenant_id = str(payload.get('tenant_id') or payload.get('tenant') or '').strip()
    business_id = str(payload.get('business_id') or '').strip()
    if not tenant_id:
        deny_autonomy_execution(
            executor=executor,
            env=env,
            reason='autonomy_safety_denied:missing_runtime_identity',
            payload=payload,
        )
    ensure_tenant_runtime_contracts(executor=executor, tenant_id=tenant_id)
    tenant_registry = getattr(executor, '_tenant_registry', None)
    if tenant_registry is not None and hasattr(tenant_registry, 'assert_active'):
        try:
            tenant_registry.assert_active(tenant_id)
        except Exception:
            deny_autonomy_execution(
                executor=executor,
                env=env,
                reason='autonomy_safety_denied:inactive_tenant',
                payload=payload,
            )

    previous_feedback = executor._safe_dict(payload.get('previous_feedback'))
    budget_guard = getattr(executor, '_tenant_execution_budget_guard', None)
    budget_verdict = None
    usage = None
    if budget_guard is not None and tenant_id:
        usage = TenantExecutionBudgetGuard.from_execution_payload(tenant_id=tenant_id, payload=payload)
        budget_verdict = budget_guard.evaluate(usage=usage)
        if not budget_verdict.allowed:
            deny_autonomy_execution(
                executor=executor,
                env=env,
                reason=f'tenant_execution_budget_denied:{budget_verdict.reason}',
                payload=payload,
            )
    economy = executor._safe_dict(payload.get('economy'))
    constraints = executor._safe_dict(payload.get('constraints'))
    cost_envelope = extract_runtime_autonomy_cost_envelope(
        payload=payload,
        economy=economy,
        constraints=constraints,
        policy=DEFAULT_RUNTIME_AUTONOMY_GATE_POLICY,
    )
    if cost_envelope.exceeds_run_budget:
        deny_autonomy_execution(
            executor=executor,
            env=env,
            reason='autonomy_safety_denied:action_budget_exceeded',
            payload=payload,
        )

    synthetic_request = SimpleNamespace(
        tenant_id=tenant_id or 'default',
        business_id=business_id,
        goal=str(payload.get('goal') or payload.get('objective_name') or action_type),
        action_id=str(payload.get('action_id') or getattr(env.decision, 'decision_id', '') or ''),
        payload=payload,
        autonomy_tier=str(payload.get('autonomy_tier') or DEFAULT_RUNTIME_AUTONOMY_GATE_POLICY.default_autonomy_tier),
        approval_policy=executor._safe_dict(payload.get('approval_policy')),
        economy=economy,
        constraints=constraints,
    )

    verdict = executor._autonomy_safety_bundle.evaluate_pre_execution(
        request=synthetic_request,
        action_type=action_type,
        payload=payload,
        previous_feedback=previous_feedback,
        event_log=getattr(executor, '_events', None),
        recent_actions=list(previous_feedback.get('recent_actions') or []),
    )
    if not verdict.allowed:
        deny_autonomy_execution(
            executor=executor,
            env=env,
            reason=f'autonomy_safety_denied:{verdict.reason}',
            payload=payload,
        )
    if budget_guard is not None and tenant_id and usage is not None:
        budget_verdict = budget_guard.consume(usage=usage)
        if not budget_verdict.allowed:
            deny_autonomy_execution(
                executor=executor,
                env=env,
                reason=f'tenant_execution_budget_denied:{budget_verdict.reason}',
                payload=payload,
            )
    return budget_verdict


__all__ = [
    'deny_autonomy_execution',
    'enforce_runtime_budget_and_blast_radius',
    'ensure_tenant_runtime_contracts',
    'tenant_runtime_context',
]
