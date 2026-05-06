from __future__ import annotations

import pytest

from security.external_adapter_credentials import ExternalAdapterCredential
from security.governance_owner_factory import build_security_governance_infrastructure


def test_live_external_adapter_paths_reject_default_and_cross_tenant_credentials(tmp_path) -> None:
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')

    with pytest.raises(PermissionError):
        owner.tenant_isolation.get_tenant_active_kms_key(
            tenant_id='acme',
            key_id='tenant:acme:key-1',
            preferred_provider_name='aws-kms',
            credential=ExternalAdapterCredential(tenant_id='acme', credential_ref='default:aws-kms', provider_name='aws-kms'),
        )

    with pytest.raises(PermissionError):
        owner.tenant_isolation.get_tenant_active_kms_key(
            tenant_id='acme',
            key_id='tenant:acme:key-1',
            preferred_provider_name='gcp-kms',
            credential=ExternalAdapterCredential(tenant_id='beta', credential_ref='tenant:beta:gcp-kms:cred-1', provider_name='gcp-kms'),
        )

    with pytest.raises(PermissionError):
        owner.tenant_isolation.export_tenant_notarized_bundle(
            tenant_id='acme',
            payload={'event': 'x'},
            certification={'kind': 'security-export'},
            credential=ExternalAdapterCredential(tenant_id='beta', credential_ref='tenant:beta:local-notary:cred-1', provider_name='local-notary'),
        )
