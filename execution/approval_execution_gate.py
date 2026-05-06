from __future__ import annotations

"""Canonical execution approval gate.

This gate binds execution to the existing approval workflow and optional
one-shot operator override path. It never creates a second decision path.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from uuid import uuid4

from contracts.action_impact_contract import ActionExecutionContext, ActionImpact
from execution.approval_policy_engine import ApprovalPolicyDecision, ApprovalPolicyEngine, ApprovalPolicyInput
from execution.canonical_operator_handoff import canonical_operator_handoff
from execution.operator_override_contract import OperatorOverrideRecord
from execution.approval_gate_fingerprint import build_execution_subject_fingerprint
from execution.approval_gate_support import (
    approval_matches_execution as _approval_matches_execution,
    build_approval_request as _build_approval_request,
    build_approval_request_fingerprint as _build_approval_request_fingerprint,
    build_handoff as _build_handoff,
    new_approval_id as _new_approval_id,
    require_execution_id as _require_execution_id,
)
from governance.approval_contract import ApprovalRecord, ApprovalRequest, ApprovalStatus
from governance.approval_workflow import ApprovalWorkflow
from governance.control_plane_audit_log import GovernanceAuditEvent, GovernanceAuditLogContract, NullGovernanceAuditLog


CANON_EXECUTION_APPROVAL_GATE = True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


@dataclass(frozen=True)
class ApprovalExecutionGateDecision:
    allowed: bool
    approval_required: bool
    operator_required: bool
    approval_id: str | None = None
    used_operator_override: bool = False
    status: str = 'allowed'
    reason: str = 'allowed'
    subject_fingerprint: str | None = None
    policy: Mapping[str, object] = field(default_factory=dict)
    handoff: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            'allowed': bool(self.allowed),
            'approval_required': bool(self.approval_required),
            'operator_required': bool(self.operator_required),
            'approval_id': self.approval_id,
            'used_operator_override': bool(self.used_operator_override),
            'status': self.status,
            'reason': self.reason,
            'subject_fingerprint': self.subject_fingerprint,
            'policy': dict(self.policy),
            'handoff': dict(self.handoff),
            'metadata': dict(self.metadata),
        }


class ApprovalExecutionGate:
    def __init__(
        self,
        *,
        approval_policy_engine: ApprovalPolicyEngine,
        approval_workflow: ApprovalWorkflow,
        audit_log: GovernanceAuditLogContract | None = None,
        default_approval_ttl_minutes: int = 120,
    ) -> None:
        self._approval_policy_engine = approval_policy_engine
        self._approval_workflow = approval_workflow
        self._audit_log = audit_log or NullGovernanceAuditLog()
        self._default_approval_ttl_minutes = max(1, int(default_approval_ttl_minutes))

    def evaluate(
        self,
        *,
        ctx: ActionExecutionContext,
        impact: ActionImpact,
        autonomy_tier: str = 'supervised',
        external_confirmation_mode: str = 'required',
        approval_policy: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
        approval_id: str | None = None,
        operator_override: OperatorOverrideRecord | None = None,
        requested_by: str | None = None,
    ) -> ApprovalExecutionGateDecision:
        ctx.validate()
        impact.validate()
        meta = _safe_dict(metadata)
        safe_policy = _safe_dict(approval_policy)

        try:
            execution_id = _require_execution_id(ctx)
        except Exception as exc:
            verdict = self._deny(
                ctx=ctx,
                execution_id='',
                decision_id='',
                subject_fingerprint=None,
                reason=f'approval_gate_invalid_execution_id:{type(exc).__name__}',
                policy={},
                autonomy_tier=autonomy_tier,
                approval_id=None,
                approval_required=False,
                operator_required=False,
            )
            self._audit(ctx.tenant_id, 'execution_approval_gate_denied', verdict.to_dict())
            return verdict

        decision_id = _text(meta.get('decision_id') or _safe_dict(ctx.metadata).get('decision_id'))
        if not decision_id:
            verdict = self._deny(
                ctx=ctx,
                execution_id=execution_id,
                decision_id='',
                subject_fingerprint=None,
                reason='approval_gate_requires_explicit_decision_id',
                policy={},
                autonomy_tier=autonomy_tier,
                approval_id=None,
                approval_required=False,
                operator_required=False,
            )
            self._audit(ctx.tenant_id, 'execution_approval_gate_denied', verdict.to_dict())
            return verdict

        try:
            subject_fingerprint = build_execution_subject_fingerprint(
                ctx=ctx,
                decision_id=decision_id,
                impact=impact,
                external_confirmation_mode=external_confirmation_mode,
            )
        except Exception as exc:
            verdict = self._deny(
                ctx=ctx,
                execution_id=execution_id,
                decision_id=decision_id,
                subject_fingerprint=None,
                reason=f'approval_gate_subject_fingerprint_error:{type(exc).__name__}',
                policy={},
                autonomy_tier=autonomy_tier,
                approval_id=None,
                approval_required=False,
                operator_required=False,
            )
            self._audit(ctx.tenant_id, 'execution_approval_gate_denied', verdict.to_dict())
            return verdict

        requested_by_actor = _text(
            requested_by or meta.get('actor_id') or _safe_dict(ctx.metadata).get('actor_id') or ctx.user_id or 'system'
        )

        policy_decision = self._approval_policy_engine.evaluate(
            ApprovalPolicyInput(
                ctx=ctx,
                impact=impact,
                autonomy_tier=autonomy_tier,
                external_confirmation_mode=external_confirmation_mode,
                approval_policy=safe_policy,
                metadata=meta,
            )
        )

        if not policy_decision.approval_required and not policy_decision.operator_required:
            verdict = ApprovalExecutionGateDecision(
                allowed=True,
                approval_required=False,
                operator_required=False,
                status='allowed',
                reason='approval_gate_not_required',
                subject_fingerprint=subject_fingerprint,
                policy=policy_decision.to_dict(),
                metadata={'execution_id': execution_id, 'decision_id': decision_id},
            )
            self._audit(ctx.tenant_id, 'execution_approval_gate_allowed', verdict.to_dict())
            return verdict

        if operator_override is not None:
            override_verdict = self._evaluate_operator_override(
                operator_override=operator_override,
                policy=policy_decision,
                ctx=ctx,
                execution_id=execution_id,
                decision_id=decision_id,
                subject_fingerprint=subject_fingerprint,
            )
            if override_verdict is not None:
                self._audit(ctx.tenant_id, 'execution_approval_gate_override_evaluated', override_verdict.to_dict())
                return override_verdict

        normalized_approval_id = _text(approval_id or meta.get('approval_id') or _safe_dict(ctx.metadata).get('approval_id')) or None
        if normalized_approval_id:
            record = self._approval_workflow.get(normalized_approval_id)
            verdict = self._evaluate_existing_approval(
                record=record,
                approval_id=normalized_approval_id,
                ctx=ctx,
                policy=policy_decision,
                autonomy_tier=autonomy_tier,
                decision_id=decision_id,
                execution_id=execution_id,
                subject_fingerprint=subject_fingerprint,
            )
            self._audit(ctx.tenant_id, 'execution_approval_gate_existing_approval_evaluated', verdict.to_dict())
            return verdict

        if policy_decision.auto_submit_approval:
            record = self._submit_approval_request(
                ctx=ctx,
                impact=impact,
                policy=policy_decision,
                requested_by=requested_by_actor,
                execution_id=execution_id,
                decision_id=decision_id,
                autonomy_tier=autonomy_tier,
                external_confirmation_mode=external_confirmation_mode,
                subject_fingerprint=subject_fingerprint,
            )
            verdict = self._deny(
                ctx=ctx,
                execution_id=execution_id,
                decision_id=decision_id,
                subject_fingerprint=subject_fingerprint,
                reason='approval_submitted_awaiting_operator',
                policy=policy_decision.to_dict(),
                autonomy_tier=autonomy_tier,
                approval_id=record.request.approval_id,
                metadata={
                    'approval_status': record.status.value,
                    'approval_request_fingerprint': _text(_safe_dict(record.request.metadata).get('approval_request_fingerprint')),
                    'expires_at': None if record.request.expires_at is None else record.request.expires_at.isoformat(),
                },
                approval_required=bool(policy_decision.approval_required),
                operator_required=bool(policy_decision.operator_required),
            )
            self._audit(ctx.tenant_id, 'execution_approval_gate_approval_submitted', verdict.to_dict())
            return verdict

        verdict = self._deny(
            ctx=ctx,
            execution_id=execution_id,
            decision_id=decision_id,
            subject_fingerprint=subject_fingerprint,
            reason='approval_required_no_approval_id',
            policy=policy_decision.to_dict(),
            autonomy_tier=autonomy_tier,
            approval_id=None,
        )
        self._audit(ctx.tenant_id, 'execution_approval_gate_denied', verdict.to_dict())
        return verdict

    def _evaluate_existing_approval(
        self,
        *,
        record: ApprovalRecord | None,
        approval_id: str,
        ctx: ActionExecutionContext,
        policy: ApprovalPolicyDecision,
        autonomy_tier: str,
        decision_id: str,
        execution_id: str,
        subject_fingerprint: str,
    ) -> ApprovalExecutionGateDecision:
        if record is None:
            return self._deny(
                ctx=ctx,
                execution_id=execution_id,
                decision_id=decision_id,
                subject_fingerprint=subject_fingerprint,
                reason='approval_not_found',
                policy=policy.to_dict(),
                autonomy_tier=autonomy_tier,
                approval_id=approval_id,
            )
        if not _approval_matches_execution(
            record=record,
            ctx=ctx,
            decision_id=decision_id,
            subject_fingerprint=subject_fingerprint,
        ):
            return self._deny(
                ctx=ctx,
                execution_id=execution_id,
                decision_id=decision_id,
                subject_fingerprint=subject_fingerprint,
                reason='approval_subject_mismatch',
                policy=policy.to_dict(),
                autonomy_tier=autonomy_tier,
                approval_id=approval_id,
            )
        if record.status is ApprovalStatus.APPROVED:
            return ApprovalExecutionGateDecision(
                allowed=True,
                approval_required=True,
                operator_required=False,
                approval_id=approval_id,
                status='allowed',
                reason='approval_satisfied',
                subject_fingerprint=subject_fingerprint,
                policy=policy.to_dict(),
                metadata={
                    'approval_status': record.status.value,
                    'execution_id': execution_id,
                    'decision_id': decision_id,
                },
            )
        return self._deny(
            ctx=ctx,
            execution_id=execution_id,
            decision_id=decision_id,
            subject_fingerprint=subject_fingerprint,
            reason=f'approval_{record.status.value}',
            policy=policy.to_dict(),
            autonomy_tier=autonomy_tier,
            approval_id=approval_id,
            metadata={'approval_status': record.status.value},
        )

    def _evaluate_operator_override(
        self,
        *,
        operator_override: OperatorOverrideRecord,
        policy: ApprovalPolicyDecision,
        ctx: ActionExecutionContext,
        execution_id: str,
        decision_id: str,
        subject_fingerprint: str,
    ) -> ApprovalExecutionGateDecision | None:
        autonomy_tier = _text(policy.metadata.get('autonomy_tier'), default='supervised')
        if not policy.manual_override_allowed:
            return self._deny(
                ctx=ctx,
                execution_id=execution_id,
                decision_id=decision_id,
                subject_fingerprint=subject_fingerprint,
                reason='manual_override_disallowed_by_policy',
                policy=policy.to_dict(),
                autonomy_tier=autonomy_tier,
                approval_id=None,
                used_operator_override=False,
            )
        try:
            operator_override.validate_binding(
                tenant_id=ctx.tenant_id,
                execution_id=execution_id,
                decision_id=decision_id,
                action_name=ctx.action_name,
                subject_fingerprint=subject_fingerprint,
            )
        except Exception as exc:
            return self._deny(
                ctx=ctx,
                execution_id=execution_id,
                decision_id=decision_id,
                subject_fingerprint=subject_fingerprint,
                reason=f'operator_override_invalid:{type(exc).__name__}',
                policy=policy.to_dict(),
                autonomy_tier=autonomy_tier,
                approval_id=None,
                metadata={'override_id': operator_override.request.override_id},
                used_operator_override=False,
            )
        if operator_override.approved_once:
            return ApprovalExecutionGateDecision(
                allowed=True,
                approval_required=bool(policy.approval_required),
                operator_required=False,
                used_operator_override=True,
                status='allowed',
                reason='operator_override_approved_once',
                subject_fingerprint=subject_fingerprint,
                policy=policy.to_dict(),
                metadata={
                    'override_id': operator_override.request.override_id,
                    'execution_id': execution_id,
                    'decision_id': decision_id,
                },
            )
        return self._deny(
            ctx=ctx,
            execution_id=execution_id,
            decision_id=decision_id,
            subject_fingerprint=subject_fingerprint,
            reason=f'operator_override_{operator_override.status.value}',
            policy=policy.to_dict(),
            autonomy_tier=autonomy_tier,
            approval_id=None,
            metadata={'override_id': operator_override.request.override_id},
            used_operator_override=False,
        )

    def _submit_approval_request(
        self,
        *,
        ctx: ActionExecutionContext,
        impact: ActionImpact,
        policy: ApprovalPolicyDecision,
        requested_by: str,
        execution_id: str,
        decision_id: str,
        autonomy_tier: str,
        external_confirmation_mode: str,
        subject_fingerprint: str,
    ) -> ApprovalRecord:
        expires_at = _utc_now() + timedelta(minutes=self._default_approval_ttl_minutes)
        request = _build_approval_request(
            ctx=ctx,
            impact=impact,
            policy=policy,
            requested_by=requested_by,
            execution_id=execution_id,
            decision_id=decision_id,
            autonomy_tier=autonomy_tier,
            external_confirmation_mode=external_confirmation_mode,
            subject_fingerprint=subject_fingerprint,
            approval_id=_new_approval_id(ctx=ctx, execution_id=execution_id),
            expires_at=expires_at,
        )
        return self._approval_workflow.submit(request)


    def _deny(
        self,
        *,
        ctx: ActionExecutionContext,
        execution_id: str,
        decision_id: str,
        subject_fingerprint: str | None,
        reason: str,
        policy: Mapping[str, object],
        autonomy_tier: str,
        approval_id: str | None,
        metadata: Mapping[str, object] | None = None,
        used_operator_override: bool = False,
        approval_required: bool = True,
        operator_required: bool = True,
    ) -> ApprovalExecutionGateDecision:
        handoff = _build_handoff(
            ctx=ctx,
            execution_id=execution_id,
            decision_id=decision_id,
            autonomy_tier=autonomy_tier,
            reason=reason,
            approval_id=approval_id,
            policy=policy,
        )
        return ApprovalExecutionGateDecision(
            allowed=False,
            approval_required=bool(approval_required),
            operator_required=bool(operator_required),
            approval_id=approval_id,
            used_operator_override=used_operator_override,
            status='approval_required',
            reason=reason,
            subject_fingerprint=subject_fingerprint,
            policy=dict(policy),
            handoff=handoff,
            metadata={'execution_id': execution_id, 'decision_id': decision_id, **dict(_safe_dict(metadata))},
        )

    def _audit(self, tenant_id: str, event_type: str, payload: Mapping[str, object]) -> None:
        self._audit_log.append(
            GovernanceAuditEvent(
                event_type=event_type,
                tenant_id=_text(tenant_id),
                emitted_at=_utc_now(),
                payload=dict(_safe_dict(payload)),
            )
        )


__all__ = [
    'ApprovalExecutionGate',
    'ApprovalExecutionGateDecision',
    'CANON_EXECUTION_APPROVAL_GATE',
    'build_execution_subject_fingerprint',
]
