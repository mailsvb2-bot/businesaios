from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Sequence

from compliance.action_compliance_policy import ActionComplianceInput, ActionCompliancePolicy
from compliance.base import PolicyMetadata


class ApprovalRequirement(str, Enum):
    NONE = 'none'
    ONE_PERSON = 'one_person'
    TWO_PERSON = 'two_person'


@dataclass(frozen=True)
class ApprovalComplianceInput:
    action: ActionComplianceInput
    estimated_budget_impact: float = 0.0
    external_data_transfer: bool = False
    cross_region_transfer: bool = False
    requested_approvals: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalComplianceVerdict:
    allowed: bool
    minimum_requirement: ApprovalRequirement
    approver_count: int
    required_reviews: tuple[str, ...]
    blocking_conditions: tuple[str, ...]
    reason: str
    policy: PolicyMetadata


class ApprovalCompliancePolicy:
    def __init__(
        self,
        action_policy: Optional[ActionCompliancePolicy] = None,
        high_budget_threshold: float = 1000.0,
        critical_budget_threshold: float = 10000.0,
        privileged_scopes: Optional[Sequence[str]] = None,
        *,
        policy_version: str = '2.0',
    ) -> None:
        self._action_policy = action_policy or ActionCompliancePolicy(policy_version=policy_version)
        self._high_budget_threshold = high_budget_threshold
        self._critical_budget_threshold = critical_budget_threshold
        self._privileged_scopes = {x.lower() for x in (privileged_scopes or ('finance', 'identity', 'security'))}
        self._policy = PolicyMetadata(
            policy_name='approval_compliance_policy',
            policy_version=policy_version,
            tags=('approval', 'guard'),
        )

    def evaluate(self, payload: ApprovalComplianceInput) -> ApprovalComplianceVerdict:
        action_verdict = self._action_policy.evaluate(payload.action)
        if not action_verdict.allowed:
            return ApprovalComplianceVerdict(
                allowed=False,
                minimum_requirement=ApprovalRequirement.NONE,
                approver_count=0,
                required_reviews=(),
                blocking_conditions=('underlying_action_denied',),
                reason='Approval denied because the underlying action is not compliant.',
                policy=self._policy,
            )

        required_reviews: list[str] = []
        approver_count = 0
        minimum_requirement = ApprovalRequirement.NONE

        if payload.action.action_scope.lower() in self._privileged_scopes:
            approver_count = max(approver_count, 1)
            minimum_requirement = ApprovalRequirement.ONE_PERSON
        if payload.action.destructive or payload.estimated_budget_impact >= self._high_budget_threshold:
            approver_count = max(approver_count, 1)
            minimum_requirement = ApprovalRequirement.ONE_PERSON
        if payload.estimated_budget_impact >= self._critical_budget_threshold:
            approver_count = max(approver_count, 2)
            minimum_requirement = ApprovalRequirement.TWO_PERSON
        if payload.external_data_transfer and payload.action.contains_pii:
            required_reviews.append('privacy')
        if payload.cross_region_transfer:
            required_reviews.append('legal')
        if payload.action.contains_secrets:
            required_reviews.append('security')
        if action_verdict.operator_required:
            approver_count = max(approver_count, 1)
            if minimum_requirement == ApprovalRequirement.NONE:
                minimum_requirement = ApprovalRequirement.ONE_PERSON

        return ApprovalComplianceVerdict(
            allowed=True,
            minimum_requirement=minimum_requirement,
            approver_count=approver_count,
            required_reviews=tuple(sorted(set(required_reviews))),
            blocking_conditions=(),
            reason='Approval requirement computed successfully.',
            policy=self._policy,
        )
