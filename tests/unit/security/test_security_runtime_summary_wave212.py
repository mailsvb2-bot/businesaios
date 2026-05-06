from security.governance_owner_factory import build_security_governance_infrastructure


def test_security_runtime_summary_exposes_governance_events(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    owner.governance.quarantine_compromised_token(token_fingerprint='tok-2', actor='secops', reason='drill')
    summary = owner.runtime_summary.build()
    assert summary.revoked_or_quarantined_entities >= 1
    assert len(summary.latest_governance_events) >= 1
