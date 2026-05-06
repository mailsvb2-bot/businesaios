from __future__ import annotations

from security.audit_export_verifier import AuditExportVerifier
from security.emergency_security_revoke import EmergencySecurityRevoke
from security.external_audit_export_signer import ExternalAuditExportSigner
from security.key_management_contract import KeyPurpose
from security.key_provider import InMemoryKeyProvider
from security.kms_provider_contract import KMSProviderCapability, KMSKeyHandle
from security.kms_provider_registry import KMSProviderRegistry
from security.mass_reencryption_executor import MassReencryptionExecutor
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.secret_contract import SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault
from security.token_revocation_store import SQLiteTokenRevocationStore


class _StubKMSProvider:
    def capability(self) -> KMSProviderCapability:
        return KMSProviderCapability(
            provider_name='stub-kms',
            supports_signing=True,
            supports_encryption=True,
            supports_rotation=True,
            supports_hsm_backed_keys=False,
        )

    def create_key(self, *, key_id: str, algorithm: str, exportable: bool = False) -> KMSKeyHandle:
        return KMSKeyHandle(provider_name='stub-kms', key_id=key_id, key_version=1, algorithm=algorithm, exportable=exportable)

    def get_active_key(self, *, key_id: str) -> KMSKeyHandle:
        return KMSKeyHandle(provider_name='stub-kms', key_id=key_id, key_version=1, algorithm='HMAC-SHA256', exportable=False)


def test_kms_provider_registry_registers_capabilities() -> None:
    registry = KMSProviderRegistry()
    entry = registry.register(_StubKMSProvider())
    assert entry.provider_name == 'stub-kms'
    assert registry.list_capabilities()[0].supports_rotation is True


def test_emergency_security_revoke_revokes_keys_and_tokens(tmp_path) -> None:
    keys = InMemoryKeyProvider()
    keys.issue_key(key_id='request-key', purpose=KeyPurpose.REQUEST_SIGNING)
    revocations = SQLiteTokenRevocationStore(str(tmp_path / 'revoked.sqlite3'))
    incidents = SQLiteSecurityIncidentRegistry(str(tmp_path / 'incidents.sqlite3'))

    report = EmergencySecurityRevoke(
        key_provider=keys,
        token_revocation_store=revocations,
        incident_registry=incidents,
    ).execute(reason='incident', key_ids=['request-key'], token_fingerprints=['tok-1'])

    assert report.success is True
    assert 'request-key' in report.revoked_key_ids
    assert revocations.is_revoked(token_fingerprint='tok-1') is True
    latest = incidents.latest(limit=1)
    assert latest[0]['incident_kind'] == 'security.emergency_revoke'


def test_audit_export_verifier_round_trip() -> None:
    signer = ExternalAuditExportSigner('secret')
    signed = signer.sign_payload(payload={'kind': 'security.export', 'items': 1})
    verifier = AuditExportVerifier('secret')
    assert verifier.verify(payload=signed['payload'], signature=signed['signature']) is True


def test_mass_reencryption_executor_rewrites_vault_records() -> None:
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', secret_name='crm-token', version='current')
    vault.seed_plaintext(ref=ref, plaintext='super-secret', source=SecretSource.MEMORY)
    report = MassReencryptionExecutor(vault=vault).run()
    assert report.success is True
    assert report.processed_records >= 1
    assert vault.get(ref) == b'super-secret'
