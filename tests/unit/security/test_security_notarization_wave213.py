from security.governance_owner_factory import build_security_governance_infrastructure


def test_external_notarization_receipt_contains_timestamp_and_ledger_anchor(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    exported = owner.export_service.export_bundle(payload={'token': 'abc'}, certification={'kind': 'security'})
    receipt = exported['notarization_receipt']
    assert receipt['timestamp_token'].startswith('tsa::')
    assert receipt['ledger_anchor_id'].startswith('ledger::')
    assert owner.export_service.verify_bundle(exported_bundle=exported) is True
