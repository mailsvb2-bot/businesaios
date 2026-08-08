from __future__ import annotations

from dataclasses import replace

import pytest

from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest, ApprovalStatus
from governance.approval_store import PersistentApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.kill_switch_registry import KillSwitchEntry, PersistentKillSwitchRegistry, _utc_now
from governance.rbac_contract import Permission, RoleId
from governance.tenant_policy_overrides import (
    PersistentTenantPolicyOverrideRegistry,
    TenantPolicyOverride,
)


def test_persistent_approval_store_roundtrip(tmp_path) -> None:
    path = tmp_path / "approvals.json"
    store = PersistentApprovalStore(path)
    workflow = ApprovalWorkflow(store=store)
    workflow.submit(
        ApprovalRequest(
            approval_id="ap-1",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="exec-1",
            requested_by="requester",
            reason="need approval",
            required_role_groups=((RoleId.OWNER,),),
        )
    )
    workflow.decide(
        ApprovalDecision(
            approval_id="ap-1",
            tenant_id="tenant-a",
            actor_id="owner-1",
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale="approved",
        )
    )

    reloaded = PersistentApprovalStore(path)
    record = reloaded.get("ap-1")
    assert record is not None
    assert record.status is ApprovalStatus.APPROVED
    assert record.decisions[0].actor_id == "owner-1"


def test_long_lived_persistent_approval_owners_share_durable_state(tmp_path) -> None:
    path = tmp_path / "shared_approvals.json"
    runtime_store = PersistentApprovalStore(path)
    operator_store = PersistentApprovalStore(path)
    runtime_workflow = ApprovalWorkflow(store=runtime_store)
    operator_workflow = ApprovalWorkflow(store=operator_store)

    runtime_workflow.submit(
        ApprovalRequest(
            approval_id="ap-shared",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="pricing-offer-1",
            requested_by="runtime",
            reason="offer requires approval",
            required_role_groups=((RoleId.OWNER,),),
        )
    )
    visible_to_operator = operator_store.get("ap-shared")
    assert visible_to_operator is not None
    assert visible_to_operator.status is ApprovalStatus.REQUESTED

    operator_workflow.decide(
        ApprovalDecision(
            approval_id="ap-shared",
            tenant_id="tenant-a",
            actor_id="owner-1",
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale="approved in control plane",
        )
    )
    visible_to_runtime = runtime_store.get("ap-shared")
    assert visible_to_runtime is not None
    assert visible_to_runtime.status is ApprovalStatus.APPROVED
    assert visible_to_runtime.decisions[-1].actor_id == "owner-1"


def test_persistent_approval_store_rejects_stale_concurrent_save(tmp_path) -> None:
    path = tmp_path / "concurrent_approvals.json"
    store_a = PersistentApprovalStore(path)
    store_b = PersistentApprovalStore(path)
    ApprovalWorkflow(store=store_a).submit(
        ApprovalRequest(
            approval_id="ap-concurrent",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="pricing-offer-1",
            requested_by="runtime",
            reason="offer requires approval",
            required_role_groups=((RoleId.OWNER,),),
        )
    )
    snapshot_a = store_a.get("ap-concurrent")
    snapshot_b = store_b.get("ap-concurrent")
    assert snapshot_a is not None and snapshot_b is not None and snapshot_a == snapshot_b

    reject = ApprovalDecision(
        approval_id="ap-concurrent", tenant_id="tenant-a", actor_id="owner-reject",
        role_id=RoleId.OWNER, outcome=ApprovalOutcome.REJECT, rationale="reject",
    )
    rejected = replace(snapshot_a, decisions=(reject,), status=ApprovalStatus.REJECTED,
        final_reason="rejected_by_authorized_actor")
    store_a.save(rejected, expected=snapshot_a)

    approve = ApprovalDecision(
        approval_id="ap-concurrent", tenant_id="tenant-a", actor_id="owner-approve",
        role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale="approve",
    )
    stale_approved = replace(snapshot_b, decisions=(approve,), status=ApprovalStatus.APPROVED,
        final_reason="approval_requirements_satisfied")
    with pytest.raises(RuntimeError, match="approval_concurrent_update"):
        store_b.save(stale_approved, expected=snapshot_b)

    final = store_a.get("ap-concurrent")
    assert final is not None and final.status is ApprovalStatus.REJECTED
    assert final.decisions[-1].outcome is ApprovalOutcome.REJECT


def test_persistent_kill_switch_registry_roundtrip(tmp_path) -> None:
    path = tmp_path / "kill_switches.json"
    registry = PersistentKillSwitchRegistry(path)
    registry.activate(
        KillSwitchEntry(
            switch_id="sw-1",
            scope="tenant",
            scope_id="tenant-a",
            reason="incident",
            activated_by="security-1",
            activated_at=_utc_now(),
        )
    )

    reloaded = PersistentKillSwitchRegistry(path)
    blocker = reloaded.find_blocker(
        tenant_id="tenant-a",
        action_name="send_email",
        action_category="outbound",
    )
    assert blocker is not None
    assert blocker.reason == "incident"


def test_persistent_tenant_policy_override_registry_roundtrip(tmp_path) -> None:
    path = tmp_path / "tenant_overrides.json"
    registry = PersistentTenantPolicyOverrideRegistry(path)
    registry.put(
        TenantPolicyOverride(
            tenant_id="tenant-a",
            add_permissions=frozenset({Permission.VIEW_AUDIT}),
            blocked_action_names=frozenset({"dangerous_action"}),
            force_approval_for_categories=frozenset({"outbound"}),
        )
    )

    reloaded = PersistentTenantPolicyOverrideRegistry(path)
    assert reloaded.is_action_blocked(
        tenant_id="tenant-a",
        action_name="dangerous_action",
        category="outbound",
    ) is True
    effective = reloaded.effective_permissions(
        tenant_id="tenant-a",
        base_permissions=frozenset(),
    )
    assert Permission.VIEW_AUDIT in effective
    assert reloaded.forces_approval(tenant_id="tenant-a", category="outbound") is True


def test_persistent_approval_store_persists_expired_status_on_read(tmp_path) -> None:
    import time
    from datetime import timedelta

    path = tmp_path / 'approvals_expire.json'
    store = PersistentApprovalStore(path)
    workflow = ApprovalWorkflow(store=store)
    workflow.submit(
        ApprovalRequest(
            approval_id='ap-expired',
            tenant_id='tenant-a',
            subject_type='action_execution',
            subject_id='exec-expired',
            requested_by='requester',
            reason='soon expires',
            required_role_groups=((RoleId.OWNER,),),
            expires_at=_utc_now() + timedelta(milliseconds=1),
        )
    )
    time.sleep(0.01)
    record = store.get('ap-expired')
    assert record is not None
    assert record.status is ApprovalStatus.EXPIRED

    reloaded = PersistentApprovalStore(path)
    record = reloaded.get('ap-expired')
    assert record is not None
    assert record.status is ApprovalStatus.EXPIRED
