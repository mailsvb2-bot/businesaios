from __future__ import annotations

from security.governance_owner_factory import build_security_governance_infrastructure


def test_security_governance_supports_connector_secret_and_key_id_quarantine(tmp_path) -> None:
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')

    connector_secret = owner.governance.quarantine_compromised_connector_secret(
        connector_id='crm',
        secret_id='token-main',
        actor='secops',
        reason='leak',
    )
    key_report = owner.governance.quarantine_compromised_key_id(
        key_id='kms-key-1',
        actor='secops',
        reason='compromise',
    )

    assert connector_secret.success is True
    assert key_report.success is True
    assert owner.governance._quarantine_registry.is_quarantined(entity_kind='connector-secret', entity_id='crm:token-main')
    assert owner.governance._quarantine_registry.is_quarantined(entity_kind='key-id', entity_id='kms-key-1')


def test_suspicious_approval_replay_opens_incident_and_quarantines_approval(tmp_path) -> None:
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')

    approval_id = 'approval-1'
    owner.governance._approval_store.grant(approval_id=approval_id, operation_kind='key_rotate', actor='alice', payload={'tenant_id': 't1'})
    owner.replay_guard.consume(approval_id=approval_id, operation_kind='key_rotate', actor='alice')
    report = owner.governance.execute_high_risk_operation(
        operation_kind='key_rotate',
        actor='alice',
        approval_id=approval_id,
        payload={'tenant_id': 't1'},
    )

    assert report.success is False
    assert report.reason == 'approval replay detected'
    assert owner.governance._quarantine_registry.is_quarantined(entity_kind='approval', entity_id=approval_id)
