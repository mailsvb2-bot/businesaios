from __future__ import annotations

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
    from datetime import timedelta
    import time

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
