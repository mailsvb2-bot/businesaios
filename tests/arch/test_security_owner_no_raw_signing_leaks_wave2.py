from __future__ import annotations

from pathlib import Path


_ALLOWED = {
    'security/request_signing.py',
    'security/request_signature_verifier.py',
    'security/webhook_signature_verifier.py',
    'security/signed_operator_approval.py',
    'security/security_audit_chain.py',
    'security/audit_export_verifier.py',
    'security/external_audit_export_signer.py',
    'security/compliance_engine.py',
    'security/key_rotation_scheduler.py',
    'security/secret_vault.py',
    'security/secret_vault_sqlite.py',
    'security/integrations/crm_webhook_security_policy.py',
    'security/__init__.py',
    'security/governance_owner_factory.py',
}


def test_new_security_wave2_signing_logic_stays_in_owner_modules() -> None:
    offenders: list[str] = []
    for path in Path('security').rglob('*.py'):
        rel = path.as_posix()
        if rel in _ALLOWED:
            continue
        text = path.read_text(encoding='utf-8')
        if 'ExternalAuditExportSigner' in text or 'AuditExportVerifier' in text:
            offenders.append(rel)
    assert not offenders, f'wave2 signing logic escaped owner modules: {offenders}'
