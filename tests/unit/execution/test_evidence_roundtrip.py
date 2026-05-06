from application.evidence.evidence_roundtrip import EvidenceRoundtripVerifier


def test_evidence_roundtrip_verifier_checks_identity_and_total_runs() -> None:
    payload = EvidenceRoundtripVerifier().verify(memory_summary={'tenant_id': 't1', 'business_id': 'b1', 'total_runs': 2}, governance_payload={'business_memory_summary': {'tenant_id': 't1', 'business_id': 'b1', 'total_runs': 2}})
    assert payload['ok'] is True
