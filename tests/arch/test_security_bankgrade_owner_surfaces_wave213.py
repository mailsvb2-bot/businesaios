from pathlib import Path


NEW_SURFACES = {
    'security/aws_kms_adapter.py',
    'security/gcp_kms_adapter.py',
    'security/vault_transit_kms_adapter.py',
    'security/hardware_hsm_client.py',
    'security/external_timestamp_authority.py',
    'security/public_ledger_anchor.py',
    'security/security_rotation_runtime.py',
    'security/tenant_security_isolation.py',
    'security/security_pressure_monitor.py',
    'security/security_slo_model.py',
    'security/cryptographic_agility.py',
    'security/security_chaos_mode.py',
}


def test_wave213_security_surfaces_do_not_embed_plaintext_or_raw_secret_reads() -> None:
    violations = []
    for rel in NEW_SURFACES:
        text = Path(rel).read_text(encoding='utf-8')
        if 'secret_bytes' in text or 'plaintext' in text or 'decrypt(' in text:
            violations.append(rel)
    assert not violations, violations


def test_wave213_factory_wires_external_kms_notary_and_runtime_surfaces() -> None:
    text = Path('security/governance_owner_factory.py').read_text(encoding='utf-8')
    assert 'AWSKMSAdapter' in text
    assert 'GCPKMSAdapter' in text
    assert 'VaultTransitKMSAdapter' in text
    assert 'HardwareHSMClient' in text
    assert 'ExternalTimestampAuthority' in text
    assert 'PublicLedgerAnchor' in text
    assert 'SecurityPressureMonitor' in text
    assert 'SecurityChaosMode' in text
