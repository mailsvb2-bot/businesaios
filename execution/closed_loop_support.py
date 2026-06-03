from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from execution.canonical_operator_handoff import canonical_operator_handoff


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_recovery_summary(*, execution_receipt: Mapping[str, Any], reliability_trace: Mapping[str, Any]) -> dict[str, Any]:
    recovery_payload = _safe_dict(execution_receipt.get('recovery'))
    recovery_plan = _safe_dict(execution_receipt.get('recovery_plan'))
    reconciliation = _safe_dict(execution_receipt.get('reconciliation'))
    if not recovery_payload and not recovery_plan and not reconciliation:
        return {}
    summary = {
        'trace_key': str(reliability_trace.get('trace_key') or ''),
        'action': str(recovery_plan.get('recovery_action') or recovery_payload.get('action') or ''),
        'reason': str(recovery_plan.get('reason') or recovery_payload.get('reason') or ''),
        'resume_action': str(recovery_plan.get('resume_action') or recovery_payload.get('resume_action') or ''),
        'resume_stage': str(recovery_plan.get('resume_stage') or recovery_payload.get('resume_stage') or ''),
        'operator_required': bool(recovery_plan.get('operator_required') or recovery_payload.get('operator_required')),
        'delivery_hint': str(recovery_plan.get('delivery_hint') or recovery_payload.get('delivery_hint') or ''),
        'dead_letter_hint': str(recovery_plan.get('dead_letter_hint') or recovery_payload.get('dead_letter_hint') or ''),
        'operator_hint': str(recovery_plan.get('operator_hint') or recovery_payload.get('operator_hint') or ''),
        'risk_flags': list(recovery_plan.get('risk_flags') or recovery_payload.get('risk_flags') or ()),
        'anomalies': list(recovery_plan.get('anomalies') or recovery_payload.get('anomalies') or reconciliation.get('anomalies') or ()),
        'latest_stage': str(reconciliation.get('latest_stage') or recovery_payload.get('latest_stage') or ''),
        'outbox_state': str(reconciliation.get('outbox_state') or recovery_payload.get('outbox_state') or ''),
        'idempotency_state': str(reconciliation.get('idempotency_state') or recovery_payload.get('idempotency_state') or ''),
    }
    return {key: value for key, value in summary.items() if value not in ('', None) and value != []}


def derived_approval_context(*, action: Mapping[str, Any], execution_receipt: Mapping[str, Any], approval_context: Mapping[str, Any] | None) -> dict[str, Any]:
    explicit = _safe_dict(approval_context)
    if explicit:
        return explicit
    for source in (execution_receipt, action):
        candidate = _safe_dict(source.get('approval'))
        if candidate:
            return candidate
        governance_payload = _safe_dict(source.get('governance'))
        candidate = _safe_dict(governance_payload.get('approval'))
        if candidate:
            return candidate
    return {}


def normalize_approval_context(*, action: Mapping[str, Any], execution_receipt: Mapping[str, Any], approval_context: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = derived_approval_context(action=action, execution_receipt=execution_receipt, approval_context=approval_context)
    if not payload:
        return {}
    tenant_id = str(payload.get('tenant_id') or action.get('tenant_id') or execution_receipt.get('tenant_id') or '').strip()
    action_tenant_id = str(action.get('tenant_id') or '').strip()
    receipt_tenant_id = str(execution_receipt.get('tenant_id') or '').strip()
    if tenant_id and action_tenant_id and tenant_id != action_tenant_id:
        raise ValueError('approval_context_action_tenant_mismatch')
    if tenant_id and receipt_tenant_id and tenant_id != receipt_tenant_id:
        raise ValueError('approval_context_receipt_tenant_mismatch')
    decision_id = str(payload.get('decision_id') or action.get('decision_id') or execution_receipt.get('decision_id') or '').strip()
    explicit_execution_id = str(payload.get('execution_id') or '').strip()
    execution_id = explicit_execution_id or None
    subject_fingerprint = str(payload.get('subject_fingerprint') or '').strip() or None
    approval_id = str(payload.get('approval_id') or _safe_dict(payload.get('governance')).get('approval_id') or '').strip() or None
    approval_required = bool(payload.get('approval_required', False))
    operator_required = bool(payload.get('operator_required', False) or approval_required)
    reason = str(payload.get('reason') or payload.get('handoff_reason') or _safe_dict(payload.get('governance')).get('reason') or '').strip()
    handoff = _safe_dict(payload.get('handoff'))
    normalized = {
        'tenant_id': tenant_id or None,
        'decision_id': decision_id or None,
        'execution_id': execution_id or None,
        'approval_id': approval_id,
        'subject_fingerprint': subject_fingerprint,
        'approval_required': approval_required,
        'operator_required': operator_required,
        'status': str(payload.get('status') or ('approval_required' if operator_required else '')).strip() or None,
        'reason': reason or None,
        'handoff': handoff or None,
        'manual_override_used': bool(payload.get('manual_override_used', False) or payload.get('used_operator_override', False)),
        'manual_override_allowed': bool(payload.get('manual_override_allowed', False)),
    }
    if operator_required and not normalized['execution_id']:
        raise ValueError('approval_context_requires_explicit_execution_id')
    if approval_required and not normalized['decision_id']:
        raise ValueError('approval_context_requires_decision_id')
    if approval_required and not normalized['approval_id']:
        raise ValueError('approval_context_requires_approval_id')
    if operator_required and not normalized['subject_fingerprint']:
        raise ValueError('approval_context_requires_subject_fingerprint')
    return {key: value for key, value in normalized.items() if value not in ('', None)}


def build_approval_handoff(*, action: Mapping[str, Any], approval_context: Mapping[str, Any], next_tier: Mapping[str, Any]) -> dict[str, Any]:
    if not bool(approval_context.get('operator_required') or approval_context.get('approval_required')):
        return {}
    existing_handoff = _safe_dict(approval_context.get('handoff'))
    if existing_handoff:
        return canonical_operator_handoff(existing_handoff, next_tier_context=next_tier, opportunity_signals=[])
    return canonical_operator_handoff({
        'run_id': str(approval_context.get('execution_id') or action.get('run_id') or action.get('decision_id') or action.get('action_id') or ''),
        'step_index': 0,
        'decision_id': str(approval_context.get('decision_id') or action.get('decision_id') or ''),
        'action': str(action.get('action_type') or action.get('action_name') or ''),
        'autonomy_tier': str(next_tier.get('current_tier') or next_tier.get('requested_tier') or 'supervised'),
        'next_tier': str(next_tier.get('suggested_tier') or 'supervised'),
        'handoff_state': 'awaiting_operator',
        'approval_required': bool(approval_context.get('approval_required', False)),
        'blocked_by_policy': False,
        'operator_required': bool(approval_context.get('operator_required', False)),
        'manual_override_allowed': bool(approval_context.get('manual_override_allowed', False)),
        'manual_override_used': bool(approval_context.get('manual_override_used', False)),
        'handoff_reason': str(approval_context.get('reason') or ''),
        'reason': str(approval_context.get('reason') or ''),
        'approval_id': str(approval_context.get('approval_id') or ''),
        'subject_fingerprint': str(approval_context.get('subject_fingerprint') or ''),
    }, next_tier_context=next_tier, opportunity_signals=[])
