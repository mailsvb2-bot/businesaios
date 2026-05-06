from pathlib import Path


NEW_SURFACES = {
    'security/governance_journal.py',
    'security/security_drill_schedule_store.py',
    'security/security_drill_runtime.py',
    'security/external_audit_notarization.py',
    'security/immutable_audit_bundle.py',
    'security/security_runtime_summary.py',
    'security/security_audit_export_service.py',
}


def test_new_security_surfaces_do_not_read_raw_plaintext_or_secret_bytes() -> None:
    violations = []
    for rel in NEW_SURFACES:
        text = Path(rel).read_text(encoding='utf-8')
        if 'secret_bytes' in text or 'plaintext' in text or 'decrypt(' in text:
            violations.append(rel)
    assert not violations, violations


def test_new_security_surfaces_do_not_embed_raw_hmac_logic() -> None:
    violations = []
    for rel in NEW_SURFACES:
        text = Path(rel).read_text(encoding='utf-8')
        if 'hmac.new(' in text or 'compare_digest(' in text:
            violations.append(rel)
    assert not violations, violations


def test_governance_owner_factory_exposes_bankgrade_closure_surfaces() -> None:
    text = Path('security/governance_owner_factory.py').read_text(encoding='utf-8')
    assert 'SQLiteGovernanceJournal' in text
    assert 'SecurityDrillRuntime' in text
    assert 'ExternalAuditNotarizationProvider' in text
