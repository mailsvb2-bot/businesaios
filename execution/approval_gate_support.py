from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from contracts.action_impact_contract import ActionExecutionContext, ActionImpact
from execution.approval_policy_engine import ApprovalPolicyDecision
from execution.approval_gate_fingerprint import _impact_summary
from execution.canonical_operator_handoff import canonical_operator_handoff
from governance.approval_contract import ApprovalRecord, ApprovalRequest

CANON_APPROVAL_GATE_SUPPORT = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def build_approval_request_fingerprint(*, tenant_id: str, subject_fingerprint: str, required_role_groups: tuple[tuple[Any, ...], ...], min_distinct_approvers: int) -> str:
    raw = json.dumps(
        {
            'tenant_id': _text(tenant_id),
            'subject_fingerprint': _text(subject_fingerprint),
            'required_role_groups': [[str(getattr(role, 'value', role)) for role in group] for group in required_role_groups],
            'min_distinct_approvers': int(min_distinct_approvers),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def require_execution_id(ctx: ActionExecutionContext) -> str:
    execution_id = _text(ctx.execution_id or _safe_dict(ctx.metadata).get('execution_id'))
    if not execution_id:
        raise RuntimeError('approval_gate_requires_explicit_execution_id')
    return execution_id


def new_approval_id(*, ctx: ActionExecutionContext, execution_id: str) -> str:
    return f"ap-{_text(ctx.tenant_id, default='tenant')}-{execution_id}-{uuid4().hex[:10]}"


def approval_matches_execution(*, record: ApprovalRecord, ctx: ActionExecutionContext, decision_id: str, subject_fingerprint: str) -> bool:
    request = record.request
    metadata = _safe_dict(request.metadata)
    return (
        request.tenant_id == ctx.tenant_id
        and request.subject_type == 'action_execution'
        and request.subject_id == require_execution_id(ctx)
        and _text(metadata.get('decision_id')) == decision_id
        and _text(metadata.get('action_name')) == ctx.action_name
        and _text(metadata.get('subject_fingerprint')) == subject_fingerprint
    )


def build_handoff(*, ctx: ActionExecutionContext, execution_id: str, decision_id: str, autonomy_tier: str, reason: str, approval_id: str | None, policy: Mapping[str, object]) -> dict[str, object]:
    normalized_policy = _safe_dict(policy)
    return canonical_operator_handoff(
        {
            'run_id': execution_id,
            'step_index': 0,
            'decision_id': decision_id,
            'action': ctx.action_name,
            'autonomy_tier': autonomy_tier,
            'next_tier': 'supervised',
            'handoff_state': 'awaiting_operator',
            'approval_required': bool(normalized_policy.get('approval_required', True)),
            'blocked_by_policy': False,
            'operator_required': bool(normalized_policy.get('operator_required', True)),
            'manual_override_allowed': bool(normalized_policy.get('manual_override_allowed', False)),
            'handoff_reason': reason,
            'reason': reason,
            'approval_id': approval_id,
        },
        next_tier_context={
            'requested_tier': autonomy_tier,
            'current_tier': autonomy_tier,
            'ceiling_tier': 'supervised',
            'suggested_tier': 'supervised',
            'escalation_allowed': False,
            'notes': list(normalized_policy.get('reasons') or []),
        },
        opportunity_signals=[],
    )


def build_approval_request(*, ctx: ActionExecutionContext, impact: ActionImpact, policy: ApprovalPolicyDecision, requested_by: str, execution_id: str, decision_id: str, autonomy_tier: str, external_confirmation_mode: str, subject_fingerprint: str, approval_id: str, expires_at: Any) -> ApprovalRequest:
    request_fingerprint = build_approval_request_fingerprint(
        tenant_id=ctx.tenant_id,
        subject_fingerprint=subject_fingerprint,
        required_role_groups=policy.required_role_groups,
        min_distinct_approvers=policy.min_distinct_approvers,
    )
    return ApprovalRequest(
        approval_id=approval_id,
        tenant_id=ctx.tenant_id,
        subject_type='action_execution',
        subject_id=execution_id,
        requested_by=requested_by,
        reason=policy.reason,
        required_role_groups=policy.required_role_groups,
        min_distinct_approvers=policy.min_distinct_approvers,
        prohibit_self_approval=True,
        expires_at=expires_at,
        metadata={
            'decision_id': decision_id,
            'action_name': ctx.action_name,
            'subject_fingerprint': subject_fingerprint,
            'approval_request_fingerprint': request_fingerprint,
            'autonomy_tier': autonomy_tier,
            'external_confirmation_mode': external_confirmation_mode,
            'impact_summary': _impact_summary(impact),
            'policy': dict(policy.to_dict()),
        },
    )


__all__ = [
    'CANON_APPROVAL_GATE_SUPPORT',
    'approval_matches_execution',
    'build_approval_request',
    'build_approval_request_fingerprint',
    'build_handoff',
    'new_approval_id',
    'require_execution_id',
]
