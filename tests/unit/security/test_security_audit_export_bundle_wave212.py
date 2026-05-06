from security.governance_owner_factory import build_security_governance_infrastructure


def test_security_audit_export_bundle_is_notarized_and_verifiable(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    exported = owner.export_service.export_bundle(payload={'token': 'abc', 'nested': {'password': 'pw'}}, certification={'kind': 'security'})
    assert exported['bundle']['signed_payload']['payload']['token'] == '***REDACTED***'
    assert owner.export_service.verify_bundle(exported_bundle=exported) is True
