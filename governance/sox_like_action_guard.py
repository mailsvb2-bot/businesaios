from __future__ import annotations

from runtime.service_names import RuntimeServiceName

"""
SOX-like action guard.

Canonical order:
1. RBAC
2. Emergency stop
3. Tenant override hard block
4. Change control / approval
5. Final allow

This guard must remain subordinate to:
DecisionCore -> ExecutableAction -> GovernanceGuard -> RuntimeExecutor
"""

from dataclasses import dataclass, field
from typing import Mapping

from contracts.action_impact_contract import ActionExecutionContext, ActionImpact
from governance.approval_contract import ApprovalRecord, ApprovalStatus
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.emergency_stop_guard import EmergencyStopGuard
from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import AccessRequest, ActorContext, Permission, ResourceRef
from governance.rbac_policy import RbacPolicy
from governance.tenant_policy_overrides import TenantPolicyOverrideRegistry


CANON_GOVERNANCE_SOX_LIKE_ACTION_GUARD = True


@dataclass(frozen=True)
class SoxLikeGuardVerdict:
    allowed: bool
    reason: str
    required_permission: Permission | None = None
    approval_required: bool = False
    approval_id: str | None = None
    operator_required: bool = False
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


class SoxLikeActionGuard:
    def __init__(
        self,
        *,
        rbac_policy: RbacPolicy,
        emergency_stop_guard: EmergencyStopGuard,
        approval_workflow: ApprovalWorkflow,
        change_control_policy: ChangeControlPolicy,
        tenant_overrides: TenantPolicyOverrideRegistry | None = None,
        permission_matrix: PermissionMatrix | None = None,
    ) -> None:
        self._rbac_policy = rbac_policy
        self._emergency_stop_guard = emergency_stop_guard
        self._approval_workflow = approval_workflow
        self._change_control_policy = change_control_policy
        self._tenant_overrides = tenant_overrides or TenantPolicyOverrideRegistry()
        self._permission_matrix = permission_matrix or PermissionMatrix()

    def evaluate(
        self,
        *,
        actor: ActorContext,
        ctx: ActionExecutionContext,
        impact: ActionImpact,
        approval_id: str | None = None,
    ) -> SoxLikeGuardVerdict:
        actor.validate()
        ctx.validate()
        impact.validate()

        if actor.tenant_id != ctx.tenant_id:
            return SoxLikeGuardVerdict(
                allowed=False,
                reason="cross_tenant_actor_execution_forbidden",
                operator_required=True,
                tags=("tenant_boundary",),
            )

        required_permission = self._permission_matrix.permission_for_action_category(impact.category.value)
        if required_permission is None:
            return SoxLikeGuardVerdict(
                allowed=False,
                reason="unknown_action_category_permission_mapping",
                operator_required=True,
                tags=("invalid_contract", "fail_closed"),
            )

        access_request = AccessRequest(
            actor=actor,
            permission=required_permission,
            resource=ResourceRef(
                resource_type="action_execution",
                resource_id=ctx.execution_id or ctx.action_name,
                tenant_id=ctx.tenant_id,
                attributes={"action_name": ctx.action_name},
            ),
            action_name=ctx.action_name,
            metadata={"action_category": impact.category.value},
        )
        access_verdict = self._rbac_policy.evaluate(access_request)
        if not access_verdict.allowed:
            return SoxLikeGuardVerdict(
                allowed=False,
                reason=access_verdict.reason,
                required_permission=required_permission,
                operator_required=True,
                tags=("rbac",),
                metadata=dict(access_verdict.audit_fields),
            )

        stop_verdict = self._emergency_stop_guard.evaluate(
            tenant_id=ctx.tenant_id,
            action_name=ctx.action_name,
            action_category=impact.category.value,
        )
        if not stop_verdict.allowed:
            return SoxLikeGuardVerdict(
                allowed=False,
                reason=f"emergency_stop:{stop_verdict.reason}",
                required_permission=required_permission,
                operator_required=True,
                tags=(RuntimeServiceName.KILL_SWITCH,),
                metadata={
                    "blocking_scope": stop_verdict.blocking_scope,
                    "blocking_scope_id": stop_verdict.blocking_scope_id,
                },
            )

        if self._tenant_overrides.is_action_blocked(
            tenant_id=ctx.tenant_id,
            action_name=ctx.action_name,
            category=impact.category.value,
        ):
            return SoxLikeGuardVerdict(
                allowed=False,
                reason="blocked_by_tenant_policy_override",
                required_permission=required_permission,
                operator_required=True,
                tags=("tenant_override",),
            )

        cc = self._change_control_policy.evaluate(ctx=ctx, impact=impact)
        if cc.approval_required:
            if not approval_id:
                return SoxLikeGuardVerdict(
                    allowed=False,
                    reason=cc.reason,
                    required_permission=required_permission,
                    approval_required=True,
                    operator_required=True,
                    tags=tuple(cc.tags),
                    metadata={
                        "required_role_groups": [[role.value for role in group] for group in cc.required_role_groups],
                        "min_distinct_approvers": cc.min_distinct_approvers,
                    },
                )

            approval_record = self._approval_workflow.get(approval_id)
            if approval_record is None:
                return SoxLikeGuardVerdict(
                    allowed=False,
                    reason="approval_not_found",
                    required_permission=required_permission,
                    approval_required=True,
                    approval_id=approval_id,
                    operator_required=True,
                    tags=tuple(cc.tags),
                )

            if not self._approval_matches_execution(
                record=approval_record,
                ctx=ctx,
            ):
                return SoxLikeGuardVerdict(
                    allowed=False,
                    reason="approval_subject_mismatch",
                    required_permission=required_permission,
                    approval_required=True,
                    approval_id=approval_id,
                    operator_required=True,
                    tags=("approval_binding", "fail_closed"),
                )

            if approval_record.status is not ApprovalStatus.APPROVED:
                return SoxLikeGuardVerdict(
                    allowed=False,
                    reason="approval_required_but_not_satisfied",
                    required_permission=required_permission,
                    approval_required=True,
                    approval_id=approval_id,
                    operator_required=True,
                    tags=tuple(cc.tags),
                )

        return SoxLikeGuardVerdict(
            allowed=True,
            reason="allowed",
            required_permission=required_permission,
            approval_required=cc.approval_required,
            approval_id=approval_id,
            operator_required=False,
            tags=tuple(cc.tags),
        )

    @staticmethod
    def _approval_matches_execution(
        *,
        record: ApprovalRecord,
        ctx: ActionExecutionContext,
    ) -> bool:
        expected_subject_type = "action_execution"
        expected_subject_id = ctx.execution_id or ctx.action_name
        request = record.request
        return (
            request.tenant_id == ctx.tenant_id
            and request.subject_type == expected_subject_type
            and request.subject_id == expected_subject_id
        )

    def require_allowed(
        self,
        *,
        actor: ActorContext,
        ctx: ActionExecutionContext,
        impact: ActionImpact,
        approval_id: str | None = None,
    ) -> None:
        verdict = self.evaluate(
            actor=actor,
            ctx=ctx,
            impact=impact,
            approval_id=approval_id,
        )
        if not verdict.allowed:
            raise RuntimeError(verdict.reason)


__all__ = [
    "CANON_GOVERNANCE_SOX_LIKE_ACTION_GUARD",
    "SoxLikeActionGuard",
    "SoxLikeGuardVerdict",
]
