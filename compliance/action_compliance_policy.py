from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from compliance.base import ComplianceControl, ComplianceVerdictStatus, PolicyMetadata


@dataclass(frozen=True)
class ActionComplianceInput:
    action_type: str
    action_scope: str
    actor_type: str
    tenant_id: Optional[str]
    region: Optional[str]
    connector_name: Optional[str]
    contains_pii: bool = False
    contains_secrets: bool = False
    evidence_required: bool = True
    outbound_effect: bool = False
    destructive: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionComplianceVerdict:
    status: ComplianceVerdictStatus
    reason: str
    required_controls: tuple[ComplianceControl, ...]
    blocked_by: tuple[str, ...]
    compliance_tags: tuple[str, ...]
    policy: PolicyMetadata

    @property
    def allowed(self) -> bool:
        return self.status != ComplianceVerdictStatus.DENIED

    @property
    def operator_required(self) -> bool:
        return self.status == ComplianceVerdictStatus.OPERATOR_REQUIRED


class ActionCompliancePolicy:
    def __init__(
        self,
        forbidden_action_types: Optional[Sequence[str]] = None,
        restricted_scopes: Optional[Sequence[str]] = None,
        *,
        policy_version: str = '2.0',
    ) -> None:
        self._forbidden_action_types = {x.lower() for x in (forbidden_action_types or ())}
        self._restricted_scopes = {
            x.lower() for x in (restricted_scopes or ('finance', 'billing', 'identity', 'security', 'compliance'))
        }
        self._policy = PolicyMetadata(
            policy_name='action_compliance_policy',
            policy_version=policy_version,
            tags=('action', 'guard'),
        )

    def evaluate(self, data: ActionComplianceInput) -> ActionComplianceVerdict:
        blocked_by: list[str] = []
        controls: list[ComplianceControl] = []
        tags: list[str] = []

        if not data.action_type.strip():
            blocked_by.append('empty_action_type')
        if not data.action_scope.strip():
            blocked_by.append('empty_action_scope')
        if data.action_type.lower() in self._forbidden_action_types:
            blocked_by.append('forbidden_action_type')

        if data.contains_secrets:
            controls.extend([ComplianceControl.PAYLOAD_REDACTION, ComplianceControl.SECRET_REDACTION])
            tags.append('secret-bearing')
        if data.contains_pii:
            controls.append(ComplianceControl.PII_REDACTION)
            tags.append('pii')
        if data.outbound_effect:
            controls.extend([ComplianceControl.EFFECT_AUDIT, ComplianceControl.IDEMPOTENCY_KEY])
            tags.append('outbound')
        if data.destructive:
            controls.extend([ComplianceControl.ROLLBACK_OR_COMPENSATION, ComplianceControl.APPROVAL])
            tags.append('destructive')
        if data.action_scope.lower() in self._restricted_scopes:
            controls.append(ComplianceControl.RESTRICTED_SCOPE_GUARD)
            tags.append(f'scope:{data.action_scope.lower()}')
        if data.evidence_required:
            controls.append(ComplianceControl.EVIDENCE_VERIFICATION)

        if blocked_by:
            return ActionComplianceVerdict(
                status=ComplianceVerdictStatus.DENIED,
                reason='Action blocked by compliance policy.',
                required_controls=tuple(sorted(set(controls), key=lambda x: x.value)),
                blocked_by=tuple(sorted(set(blocked_by))),
                compliance_tags=tuple(sorted(set(tags))),
                policy=self._policy,
            )

        if data.actor_type.lower() in {'autonomous', 'agent', 'system'} and (
            data.destructive or data.action_scope.lower() in self._restricted_scopes
        ):
            return ActionComplianceVerdict(
                status=ComplianceVerdictStatus.OPERATOR_REQUIRED,
                reason='Operator approval required for autonomous restricted or destructive action.',
                required_controls=tuple(sorted(set(controls), key=lambda x: x.value)),
                blocked_by=(),
                compliance_tags=tuple(sorted(set(tags))),
                policy=self._policy,
            )

        return ActionComplianceVerdict(
            status=ComplianceVerdictStatus.ALLOWED,
            reason='Action passed compliance policy.',
            required_controls=tuple(sorted(set(controls), key=lambda x: x.value)),
            blocked_by=(),
            compliance_tags=tuple(sorted(set(tags))),
            policy=self._policy,
        )
