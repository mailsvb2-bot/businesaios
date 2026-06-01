from __future__ import annotations

from bootstrap.safety_control_boot import build_safety_control_runtime
from core.safety.controls.action_identity import canonical_action_id
from core.safety.controls.multi_step_approval.models import ApprovalTicket, ApprovalWorkflowState
from runtime.safety_controls import (
    build_runtime_safety_context,
    evaluate_runtime_action_controls,
    record_action_failure,
    record_action_success,
)


def test_safety_manifest_chain_and_rollback_reconcile_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_SAFETY_PERSISTENT', '0')
    build_safety_control_runtime.cache_clear()
    runtime = build_safety_control_runtime(persistent=False)
    resolver = runtime.profile.tenant_policy_resolver
    manifest = resolver.manifest_for('tenant-wave221', 'safety_profile')
    assert runtime.profile.policy_manifest_signer.verify(manifest) is True
    assert runtime.profile.policy_trust_chain.verify_lineage(
        tenant_id='tenant-wave221',
        policy_scope='safety_profile',
    ) is True

    payload = {
        'tenant_id': 'tenant-wave221',
        'rollback_verification_required': True,
        'rollback_expected_state': {'mode': 'safe'},
        'rollback_observed_state': {'mode': 'safe'},
    }
    record_action_failure(action='ops.rollback.deploy', payload=payload)
    record_action_success(action='ops.rollback.deploy', payload=payload)
    action_id = canonical_action_id(
        action='ops.rollback.deploy',
        tenant_id='tenant-wave221',
        payload=payload,
    )
    plan = runtime.profile.rollback_planner.get_persisted(
        tenant_id='tenant-wave221',
        action_id=action_id,
    )
    assert plan is not None
    assert str(plan.reconciliation_state.value) == 'verified'
    assert len(plan.receipts) >= 1


def test_partial_approval_state_is_persisted_and_blocks_until_quorum(monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_SAFETY_PERSISTENT', '0')
    build_safety_control_runtime.cache_clear()
    runtime = build_safety_control_runtime(persistent=False)
    payload = {'tenant_id': 'tenant-wave221', 'approval_required': True}
    ctx = build_runtime_safety_context(action='pricing.publish_offer', payload=payload)
    action_id = canonical_action_id(action=ctx.action, tenant_id=ctx.tenant_id, payload=ctx.payload)
    runtime.profile.approval_repository.put(ApprovalTicket(action_id=action_id, required_approvals=2))
    runtime.profile.approval_repository.record_approval(action_id=action_id, approver='alice')
    decision = [
        d for d in evaluate_runtime_action_controls(action=ctx.action, payload=payload)
        if d.control == 'multi_step_approval'
    ][0]
    assert decision.reason == 'insufficient_approvals'
    ticket = runtime.profile.approval_repository.get(action_id)
    assert ticket.state in {
        ApprovalWorkflowState.PARTIALLY_APPROVED,
        ApprovalWorkflowState.PENDING,
        ApprovalWorkflowState.REQUESTED,
    }
