from __future__ import annotations

from pathlib import Path

from security.governance_owner_factory import build_security_governance_infrastructure


def test_security_governance_factory_builds_owner_bundle(tmp_path: Path) -> None:
    infra = build_security_governance_infrastructure(
        base_dir=tmp_path / 'sec',
        shared_secret='secret',
    )
    assert infra.governance is not None
    assert infra.recovery is not None
    assert infra.export_service is not None
    assert infra.replay_guard is not None


def test_signed_approval_is_single_use_via_replay_guard(tmp_path: Path) -> None:
    infra = build_security_governance_infrastructure(
        base_dir=tmp_path / 'sec',
        shared_secret='secret',
    )
    approvals = tmp_path / 'sec' / 'signed_operator_approvals.sqlite3'
    # approval store is inside governance factory; use governance-owned approval store through bundle side effect
    from security.signed_operator_approval import SignedOperatorApprovalStore

    store = SignedOperatorApprovalStore(str(approvals), 'secret')
    store.grant(
        approval_id='a1',
        operation_kind='key_rotate',
        actor='alice',
        payload={'ticket': 'SEC-1'},
    )

    first = infra.governance.execute_high_risk_operation(
        operation_kind='key_rotate',
        actor='alice',
        approval_id='a1',
        payload={'target': 'master-key'},
    )
    assert first.success is True

    second = infra.governance.execute_high_risk_operation(
        operation_kind='key_rotate',
        actor='alice',
        approval_id='a1',
        payload={'target': 'master-key'},
    )
    assert second.success is False
    assert second.phase == 'approval'
    assert 'replay' in second.reason
