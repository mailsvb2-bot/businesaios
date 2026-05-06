from __future__ import annotations

"""
Change control policy.

This layer only determines whether the already-selected action
requires human approval before execution.
"""

from dataclasses import dataclass, field

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from governance.rbac_contract import RoleId
from governance.tenant_policy_overrides import TenantPolicyOverrideRegistry


CANON_GOVERNANCE_CHANGE_CONTROL_POLICY = True


@dataclass(frozen=True)
class ChangeControlDecision:
    approval_required: bool
    reason: str
    required_role_groups: tuple[tuple[RoleId, ...], ...] = ()
    min_distinct_approvers: int = 1
    tags: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


class ChangeControlPolicy:
    def __init__(
        self,
        *,
        tenant_overrides: TenantPolicyOverrideRegistry | None = None,
        budget_minor_threshold: int = 50_000,
        outbound_count_threshold: int = 1,
        publication_count_threshold: int = 1,
    ) -> None:
        self._tenant_overrides = tenant_overrides or TenantPolicyOverrideRegistry()
        self._budget_minor_threshold = int(budget_minor_threshold)
        self._outbound_count_threshold = int(outbound_count_threshold)
        self._publication_count_threshold = int(publication_count_threshold)

    def evaluate(
        self,
        *,
        ctx: ActionExecutionContext,
        impact: ActionImpact,
    ) -> ChangeControlDecision:
        ctx.validate()
        impact.validate()

        if self._tenant_overrides.forces_approval(
            tenant_id=ctx.tenant_id,
            category=impact.category.value,
        ):
            return ChangeControlDecision(
                approval_required=True,
                reason="forced_by_tenant_policy_override",
                required_role_groups=((RoleId.OWNER,),),
                min_distinct_approvers=1,
                tags=("tenant_override",),
            )

        if impact.category in {ActionCategory.UNKNOWN}:
            return ChangeControlDecision(
                approval_required=True,
                reason="unknown_action_category_fail_closed",
                required_role_groups=((RoleId.OWNER,), (RoleId.SECURITY,)),
                min_distinct_approvers=2,
                tags=("fail_closed", "unknown_category"),
            )

        if impact.category is ActionCategory.SAFE_READ:
            return ChangeControlDecision(
                approval_required=False,
                reason="safe_read_no_approval",
                tags=("safe_read",),
            )

        if impact.category is ActionCategory.INTERNAL_WRITE:
            return ChangeControlDecision(
                approval_required=False,
                reason="internal_write_allowed_under_controls",
                tags=("internal_write",),
            )

        if impact.category in {ActionCategory.BUDGET_CHANGE} or int(impact.cost_minor) >= self._budget_minor_threshold:
            return ChangeControlDecision(
                approval_required=True,
                reason="finance_change_requires_dual_control",
                required_role_groups=((RoleId.OWNER,), (RoleId.FINANCE,)),
                min_distinct_approvers=2,
                tags=("finance", "dual_control"),
            )

        if impact.category in {ActionCategory.STRATEGIC_CHANGE, ActionCategory.ROLLBACK}:
            return ChangeControlDecision(
                approval_required=True,
                reason="high_impact_change_requires_dual_control",
                required_role_groups=((RoleId.OWNER,), (RoleId.SECURITY,)),
                min_distinct_approvers=2,
                tags=("strategic", "dual_control"),
            )

        if impact.category is ActionCategory.PUBLICATION and (
            impact.requires_human_approval or int(impact.publication_count) >= self._publication_count_threshold
        ):
            return ChangeControlDecision(
                approval_required=True,
                reason="publication_requires_human_review",
                required_role_groups=((RoleId.OWNER, RoleId.OPERATOR),),
                min_distinct_approvers=1,
                tags=("publication", "effectful"),
            )

        if impact.category is ActionCategory.OUTBOUND and (
            impact.requires_human_approval or int(impact.outbound_count) >= self._outbound_count_threshold
        ):
            return ChangeControlDecision(
                approval_required=True,
                reason="outbound_requires_human_review",
                required_role_groups=((RoleId.OWNER, RoleId.OPERATOR),),
                min_distinct_approvers=1,
                tags=("outbound", "effectful"),
            )

        if impact.category is ActionCategory.EXECUTION:
            if bool(impact.requires_human_approval):
                return ChangeControlDecision(
                    approval_required=True,
                    reason="generic_execution_flagged_for_human_review",
                    required_role_groups=((RoleId.OWNER, RoleId.OPERATOR),),
                    min_distinct_approvers=1,
                    tags=("execution", "effectful"),
                )
            return ChangeControlDecision(
                approval_required=False,
                reason="generic_execution_allowed_under_rbac_and_runtime_controls",
                tags=("execution",),
            )

        return ChangeControlDecision(
            approval_required=True,
            reason="unclassified_change_fail_closed",
            required_role_groups=((RoleId.OWNER,),),
            min_distinct_approvers=1,
            tags=("fail_closed", "unclassified"),
        )


__all__ = [
    "CANON_GOVERNANCE_CHANGE_CONTROL_POLICY",
    "ChangeControlDecision",
    "ChangeControlPolicy",
]
