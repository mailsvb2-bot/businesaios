from __future__ import annotations

import pytest

from security.governance_owner_factory import build_security_governance_infrastructure
from security.tenant_security_isolation import TenantSecurityIsolationError
from security.external_adapter_credentials import ExternalAdapterCredential


def test_tenant_isolation_binds_kms_and_notary_reads_to_tenant_scope(tmp_path) -> None:
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    kms_credential = ExternalAdapterCredential(tenant_id='acme', credential_ref='tenant:acme:hardware-hsm:cred-1', provider_name='hardware-hsm')
    notary_credential = ExternalAdapterCredential(tenant_id='acme', credential_ref='tenant:acme:local-notary:cred-1', provider_name='local-notary')

    handle = owner.tenant_isolation.get_tenant_active_kms_key(
        tenant_id='acme',
        key_id='tenant:acme:key-1',
        preferred_provider_name='hardware-hsm',
        credential=kms_credential,
    )
    assert handle.provider_name == 'hardware-hsm'
    assert handle.key_id == 'tenant:acme:key-1'

    exported = owner.tenant_isolation.export_tenant_notarized_bundle(
        tenant_id='acme',
        payload={'event': 'rotation-complete'},
        certification={'kind': 'security-export'},
        credential=notary_credential,
    )
    assert owner.tenant_isolation.verify_tenant_notarized_bundle(tenant_id='acme', exported_bundle=exported, credential=notary_credential) is True

    with pytest.raises(TenantSecurityIsolationError):
        owner.tenant_isolation.get_tenant_active_kms_key(
            tenant_id='acme',
            key_id='tenant:beta:key-2',
            preferred_provider_name='hardware-hsm',
            credential=kms_credential,
        )
    with pytest.raises(TenantSecurityIsolationError):
        owner.tenant_isolation.export_tenant_notarized_bundle(
            tenant_id='acme',
            payload={'tenant_id': 'beta', 'event': 'bad'},
            certification={'kind': 'security-export'},
            credential=notary_credential,
        )
    with pytest.raises(TenantSecurityIsolationError):
        owner.tenant_isolation.verify_tenant_notarized_bundle(tenant_id='acme', exported_bundle={
            'bundle': {
                'signed_payload': {'payload': {'tenant_id': 'beta', 'event': 'bad'}, 'signature': 'sig'},
                'certification': {'tenant_id': 'beta'},
            },
            'notarization_receipt': {},
        }, credential=notary_credential)


def test_tenant_isolation_enforces_external_adapter_credentials_on_write_paths(tmp_path) -> None:
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    kms_credential = ExternalAdapterCredential(tenant_id='acme', credential_ref='tenant:acme:aws-kms:cred-1', provider_name='aws-kms')
    bad_kms_credential = ExternalAdapterCredential(tenant_id='acme', credential_ref='default:aws-kms', provider_name='aws-kms')
    cross_kms_credential = ExternalAdapterCredential(tenant_id='beta', credential_ref='tenant:beta:aws-kms:cred-1', provider_name='aws-kms')
    notary_credential = ExternalAdapterCredential(tenant_id='acme', credential_ref='tenant:acme:local-notary:cred-1', provider_name='local-notary')

    handle = owner.tenant_isolation.create_tenant_kms_key(
        tenant_id='acme',
        key_id='tenant:acme:key-created',
        algorithm='aes256_gcm',
        preferred_provider_name='aws-kms',
        require_hsm_backed_keys=True,
        credential=kms_credential,
    )
    assert handle.provider_name == 'aws-kms'
    rotated = owner.tenant_isolation.rotate_tenant_kms_key(
        tenant_id='acme',
        key_id='tenant:acme:key-created',
        algorithm='aes256_gcm',
        preferred_provider_name='aws-kms',
        require_hsm_backed_keys=True,
        credential=kms_credential,
    )
    assert rotated.provider_name == 'aws-kms'

    with pytest.raises(PermissionError):
        owner.tenant_isolation.create_tenant_kms_key(
            tenant_id='acme',
            key_id='tenant:acme:key-created',
            algorithm='aes256_gcm',
            preferred_provider_name='aws-kms',
            credential=bad_kms_credential,
        )
    with pytest.raises(PermissionError):
        owner.tenant_isolation.rotate_tenant_kms_key(
            tenant_id='acme',
            key_id='tenant:acme:key-created',
            algorithm='aes256_gcm',
            preferred_provider_name='aws-kms',
            credential=cross_kms_credential,
        )
    with pytest.raises(PermissionError):
        owner.tenant_isolation.export_tenant_notarized_bundle(
            tenant_id='acme',
            payload={'event': 'export'},
            certification={'kind': 'security-export'},
            credential=ExternalAdapterCredential(tenant_id='acme', credential_ref='default:local-notary', provider_name='local-notary'),
        )

    exported = owner.tenant_isolation.export_tenant_notarized_bundle(
        tenant_id='acme',
        payload={'event': 'export'},
        certification={'kind': 'security-export'},
        credential=notary_credential,
    )
    assert owner.tenant_isolation.verify_tenant_notarized_bundle(tenant_id='acme', exported_bundle=exported, credential=notary_credential) is True
