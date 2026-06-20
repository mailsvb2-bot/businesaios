from __future__ import annotations

"""Canonical execution approval policy engine.

This module derives execution-time human-in-the-loop requirements from the
existing governance change-control policy and explicit execution metadata.
It never chooses actions and never bypasses governance.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from governance.change_control_policy import ChangeControlDecision, ChangeControlPolicy
from governance.rbac_contract import RoleId


CANON_EXECUTION_APPROVAL_POLICY_ENGINE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'off'}:
            return False
    return bool(value)


def _coerce_role(value: object) -> RoleId | None:
    raw = str(getattr(value, 'value', value) or '').strip().lower()
    if not raw:
        return None
    try:
        return RoleId(raw)
    except ValueError:
        return None


def _explicit_required_role_groups(value: object) -> tuple[tuple[RoleId, ...], ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        candidates: list[object] = [item.strip() for item in value.split(',')]
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates = list(value)
    else:
        candidates = [value]
    roles = tuple(dict.fromkeys(role for role in (_coerce_role(item) for item in candidates) if role is not None))
    return tuple((role,) for role in roles)


@dataclass(frozen=True)
class ApprovalPolicyInput:
    ctx: ActionExecutionContext
    impact: ActionImpact
    autonomy_tier: str = 'supervised'
    external_confirmation_mode: str = 'required'
    approval_policy: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        self.ctx.validate()
        self.impact.validate()
        if not _text(self.autonomy_tier, default='supervised'):
            raise ValueError('autonomy_tier is required')
        if not _text(self.external_confirmation_mode, default='required'):
            raise ValueError('external_confirmation_mode is required')


@dataclass(frozen=True)
class ApprovalPolicyDecision:
    approval_required: bool
    operator_required: bool
    manual_override_allowed: bool
    auto_submit_approval: bool
    approval_scope: str
    required_role_groups: tuple[tuple[RoleId, ...], ...] = ()
    min_distinct_approvers: int = 1
    reason: str = 'no_human_gate_required'
    reasons: tuple[str, ...] = ()
    governance_reason: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            'approval_required': bool(self.approval_required),
            'operator_required': bool(self.operator_required),
            'manual_override_allowed': bool(self.manual_override_allowed),
            'auto_submit_approval': bool(self.auto_submit_approval),
            'approval_scope': self.approval_scope,
            'required_role_groups': [[role.value for role in group] for group in self.required_role_groups],
            'min_distinct_approvers': int(self.min_distinct_approvers),
            'reason': self.reason,
            'reasons': list(self.reasons),
            'governance_reason': self.governance_reason,
            'metadata': dict(self.metadata),
        }


class ApprovalPolicyEngine:
    def __init__(
        self,
        *,
        change_control_policy: ChangeControlPolicy,
        low_confidence_threshold: float = 0.70,
    ) -> None:
        self._change_control_policy = change_control_policy
        self._low_confidence_threshold = float(low_confidence_threshold)

    def evaluate(self, policy_input: ApprovalPolicyInput) -> ApprovalPolicyDecision:
        policy_input.validate()
        approval_policy = _safe_dict(policy_input.approval_policy)
        meta = _safe_dict(policy_input.metadata)

        change_control = self._change_control_policy.evaluate(
            ctx=policy_input.ctx,
            impact=policy_input.impact,
        )

        approval_required = bool(change_control.approval_required)
        operator_required = bool(change_control.approval_required)
        auto_submit_approval = _safe_bool(approval_policy.get('auto_submit_approval', True))
        required_role_groups = tuple(change_control.required_role_groups)
        min_distinct_approvers = max(1, int(change_control.min_distinct_approvers or 1))
        explicit_groups = _explicit_required_role_groups(approval_policy.get('required_roles') or meta.get('required_roles'))
        reasons: list[str] = []
        if change_control.approval_required:
            reasons.append(str(change_control.reason or 'change_control_requires_approval'))

        if explicit_groups:
            approval_required = True
            operator_required = True
            required_role_groups = explicit_groups
            reasons.append('explicit_required_roles')

        if _safe_bool(approval_policy.get('force_human_approval') or meta.get('force_human_approval')):
            approval_required = True
            operator_required = True
            reasons.append('explicit_policy_force_human_approval')

        if _safe_bool(approval_policy.get('requires_manual_review') or meta.get('requires_manual_review') or meta.get('operator_required')):
            approval_required = True
            operator_required = True
            reasons.append('explicit_manual_review_required')

        mode = _text(policy_input.external_confirmation_mode, default='required').casefold()
        if mode == 'required' and policy_input.impact.category not in {ActionCategory.SAFE_READ}:
            approval_required = True
            operator_required = True
            if not required_role_groups:
                required_role_groups = ((RoleId.OWNER, RoleId.OPERATOR),)
            reasons.append('required_confirmation_mode_effectful_execution')

        require_human_on_low_confidence = _safe_bool(approval_policy.get('require_human_on_low_confidence', True))
        if require_human_on_low_confidence and float(policy_input.impact.confidence) < self._low_confidence_threshold:
            approval_required = True
            operator_required = True
            if not required_role_groups:
                required_role_groups = ((RoleId.OWNER,),)
            reasons.append('low_confidence_execution_requires_human_review')

        if policy_input.impact.category is ActionCategory.UNKNOWN:
            approval_required = True
            operator_required = True
            required_role_groups = required_role_groups or ((RoleId.OWNER,), (RoleId.SECURITY,))
            min_distinct_approvers = max(2, min_distinct_approvers)
            reasons.append('unknown_action_category_fail_closed')

        if _text(policy_input.autonomy_tier, default='supervised') == 'full_autonomy' and approval_required:
            reasons.append('approval_caps_full_autonomy')

        dual_control = min_distinct_approvers > 1 or len(required_role_groups) > 1
        sensitive_roles_present = any(role in {RoleId.SECURITY, RoleId.FINANCE} for group in required_role_groups for role in group)
        sensitive_tags = set(change_control.tags)
        high_risk_change = bool(
            dual_control
            or sensitive_roles_present
            or {'finance', 'strategic', 'dual_control', 'fail_closed'} & sensitive_tags
        )

        requested_manual_override = _safe_bool(approval_policy.get('allow_operator_override', True))
        manual_override_allowed = bool(requested_manual_override and not high_risk_change)
        if requested_manual_override and not manual_override_allowed:
            reasons.append('manual_override_disabled_for_dual_control_or_high_risk_change')

        if approval_required:
            approval_scope = 'approval'
        elif operator_required:
            approval_scope = 'operator_only'
        else:
            approval_scope = 'none'

        if approval_required and not required_role_groups:
            required_role_groups = ((RoleId.OWNER, RoleId.OPERATOR),)

        unique_reasons = tuple(dict.fromkeys(item for item in reasons if _text(item)))
        reason = unique_reasons[0] if unique_reasons else 'no_human_gate_required'

        return ApprovalPolicyDecision(
            approval_required=approval_required,
            operator_required=operator_required,
            manual_override_allowed=manual_override_allowed,
            auto_submit_approval=auto_submit_approval,
            approval_scope=approval_scope,
            required_role_groups=required_role_groups,
            min_distinct_approvers=min_distinct_approvers,
            reason=reason,
            reasons=unique_reasons,
            governance_reason=str(change_control.reason or '') or None,
            metadata={
                'autonomy_tier': _text(policy_input.autonomy_tier, default='supervised'),
                'external_confirmation_mode': mode or 'required',
                'impact_confidence': float(policy_input.impact.confidence),
                'change_control': _change_control_to_dict(change_control),
                'dual_control': dual_control,
                'high_risk_change': high_risk_change,
                'low_confidence_threshold': self._low_confidence_threshold,
                'requested_manual_override': requested_manual_override,
                'explicit_required_roles': [[role.value for role in group] for group in explicit_groups],
            },
        )


def _change_control_to_dict(decision: ChangeControlDecision) -> dict[str, object]:
    return {
        'approval_required': bool(decision.approval_required),
        'reason': decision.reason,
        'required_role_groups': [[role.value for role in group] for group in decision.required_role_groups],
        'min_distinct_approvers': int(decision.min_distinct_approvers),
        'tags': list(decision.tags),
        'metadata': dict(decision.metadata),
    }


__all__ = [
    'ApprovalPolicyDecision',
    'ApprovalPolicyEngine',
    'ApprovalPolicyInput',
    'CANON_EXECUTION_APPROVAL_POLICY_ENGINE',
]
