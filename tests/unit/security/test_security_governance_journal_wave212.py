from security.governance_owner_factory import build_security_governance_infrastructure


def test_governance_journal_tracks_quarantine_and_recovery_flow(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    quarantine = owner.governance.quarantine_compromised_token(token_fingerprint='tok-1', actor='secops', reason='detected')
    owner.governance.recover_quarantined_entity(
        incident_id=quarantine.details['incident_id'],
        entity_kind='token',
        entity_id='tok-1',
        actor='secops',
        resolution_payload={'verified': True},
    )
    timeline = owner.governance_journal.latest_entity_timeline(entity_kind='token', entity_id='tok-1')
    event_kinds = {item['event_kind'] for item in timeline}
    assert 'token.quarantined' in event_kinds
    assert 'incident.recovered' in event_kinds
