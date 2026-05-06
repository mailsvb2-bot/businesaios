from __future__ import annotations

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.emergency_stop_guard import EmergencyStopGuard
from governance.kill_switch_registry import KillSwitchEntry, KillSwitchRegistry, _utc_now
from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import ActorContext, RoleId
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog
from governance.sox_like_action_guard import SoxLikeActionGuard
from governance.tenant_policy_overrides import TenantPolicyOverrideRegistry


def build_guard() -> tuple[SoxLikeActionGuard, ApprovalWorkflow, KillSwitchRegistry]:
    approval_workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    kill_switch_registry = KillSwitchRegistry()
    guard = SoxLikeActionGuard(
        rbac_policy=RbacPolicy(
            role_catalog=RoleCatalog(),
            permission_matrix=PermissionMatrix(),
            tenant_overrides=TenantPolicyOverrideRegistry(),
        ),
        emergency_stop_guard=EmergencyStopGuard(registry=kill_switch_registry),
        approval_workflow=approval_workflow,
        change_control_policy=ChangeControlPolicy(),
        tenant_overrides=TenantPolicyOverrideRegistry(),
        permission_matrix=PermissionMatrix(),
    )
    return guard, approval_workflow, kill_switch_registry


def test_sox_guard_requires_approval_for_budget_change() -> None:
    guard, _, _ = build_guard()
    verdict = guard.evaluate(
        actor=ActorContext(
            actor_id="owner-1",
            tenant_id="tenant-a",
            role_ids=frozenset({RoleId.OWNER}),
        ),
        ctx=ActionExecutionContext(
            tenant_id="tenant-a",
            user_id="owner-1",
            action_name="change_budget",
            payload={},
            execution_id="exec-1",
        ),
        impact=ActionImpact(
            action_name="change_budget",
            category=ActionCategory.BUDGET_CHANGE,
            cost_minor=100_000,
        ),
    )
    assert verdict.allowed is False
    assert verdict.approval_required is True
    assert verdict.reason == "finance_change_requires_dual_control"


def test_sox_guard_rejects_mismatched_approval_subject() -> None:
    guard, workflow, _ = build_guard()

    workflow.submit(
        ApprovalRequest(
            approval_id="ap-1",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="another-exec",
            requested_by="requester",
            reason="budget change",
            required_role_groups=((RoleId.OWNER,), (RoleId.FINANCE,)),
            min_distinct_approvers=2,
        )
    )
    workflow.decide(
        ApprovalDecision(
            approval_id="ap-1",
            tenant_id="tenant-a",
            actor_id="owner-1",
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale="owner ok",
        )
    )
    workflow.decide(
        ApprovalDecision(
            approval_id="ap-1",
            tenant_id="tenant-a",
            actor_id="finance-1",
            role_id=RoleId.FINANCE,
            outcome=ApprovalOutcome.APPROVE,
            rationale="finance ok",
        )
    )

    verdict = guard.evaluate(
        actor=ActorContext(
            actor_id="owner-1",
            tenant_id="tenant-a",
            role_ids=frozenset({RoleId.OWNER}),
        ),
        ctx=ActionExecutionContext(
            tenant_id="tenant-a",
            user_id="owner-1",
            action_name="change_budget",
            payload={},
            execution_id="exec-1",
        ),
        impact=ActionImpact(
            action_name="change_budget",
            category=ActionCategory.BUDGET_CHANGE,
            cost_minor=100_000,
        ),
        approval_id="ap-1",
    )
    assert verdict.allowed is False
    assert verdict.reason == "approval_subject_mismatch"


def test_sox_guard_allows_when_matching_approval_is_satisfied() -> None:
    guard, workflow, _ = build_guard()

    workflow.submit(
        ApprovalRequest(
            approval_id="ap-2",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="exec-2",
            requested_by="requester",
            reason="budget change",
            required_role_groups=((RoleId.OWNER,), (RoleId.FINANCE,)),
            min_distinct_approvers=2,
        )
    )
    workflow.decide(
        ApprovalDecision(
            approval_id="ap-2",
            tenant_id="tenant-a",
            actor_id="owner-1",
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale="owner ok",
        )
    )
    workflow.decide(
        ApprovalDecision(
            approval_id="ap-2",
            tenant_id="tenant-a",
            actor_id="finance-1",
            role_id=RoleId.FINANCE,
            outcome=ApprovalOutcome.APPROVE,
            rationale="finance ok",
        )
    )

    verdict = guard.evaluate(
        actor=ActorContext(
            actor_id="owner-1",
            tenant_id="tenant-a",
            role_ids=frozenset({RoleId.OWNER}),
        ),
        ctx=ActionExecutionContext(
            tenant_id="tenant-a",
            user_id="owner-1",
            action_name="change_budget",
            payload={},
            execution_id="exec-2",
        ),
        impact=ActionImpact(
            action_name="change_budget",
            category=ActionCategory.BUDGET_CHANGE,
            cost_minor=100_000,
        ),
        approval_id="ap-2",
    )
    assert verdict.allowed is True
    assert verdict.reason == "allowed"


def test_sox_guard_is_blocked_by_emergency_stop_before_execution() -> None:
    guard, _, kill_switch_registry = build_guard()

    kill_switch_registry.activate(
        KillSwitchEntry(
            switch_id="sw-1",
            scope="tenant",
            scope_id="tenant-a",
            reason="incident",
            activated_by="security-1",
            activated_at=_utc_now(),
        )
    )

    verdict = guard.evaluate(
        actor=ActorContext(
            actor_id="owner-1",
            tenant_id="tenant-a",
            role_ids=frozenset({RoleId.OWNER}),
        ),
        ctx=ActionExecutionContext(
            tenant_id="tenant-a",
            user_id="owner-1",
            action_name="change_budget",
            payload={},
            execution_id="exec-3",
        ),
        impact=ActionImpact(
            action_name="change_budget",
            category=ActionCategory.BUDGET_CHANGE,
            cost_minor=100_000,
        ),
    )
    assert verdict.allowed is False
    assert verdict.reason == "emergency_stop:incident"
