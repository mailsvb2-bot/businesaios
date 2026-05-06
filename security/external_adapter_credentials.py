from __future__ import annotations

from dataclasses import dataclass

CANON_EXTERNAL_ADAPTER_CREDENTIALS = True


@dataclass(frozen=True)
class ExternalAdapterCredential:
    tenant_id: str
    credential_ref: str
    provider_name: str
    allow_default: bool = False

    def validate(self) -> None:
        tenant_norm = str(self.tenant_id or '').strip()
        credential_norm = str(self.credential_ref or '').strip()
        provider_norm = str(self.provider_name or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        if not provider_norm:
            raise ValueError('provider_name is required')
        if not credential_norm:
            raise ValueError('credential_ref is required')
        if credential_norm.lower().startswith('default:') and not self.allow_default:
            raise PermissionError('default external adapter credentials are forbidden')
        expected_prefix = f'tenant:{tenant_norm}:'
        if not credential_norm.startswith(expected_prefix):
            raise PermissionError('cross-tenant external adapter credential denied')


def assert_external_adapter_credential(*, tenant_id: str, credential: ExternalAdapterCredential | None, provider_name: str) -> ExternalAdapterCredential:
    if credential is None:
        raise PermissionError(f'{provider_name} credential is required')
    if str(credential.provider_name or '').strip() != str(provider_name or '').strip():
        raise PermissionError(f'{provider_name} credential provider mismatch')
    if str(credential.tenant_id or '').strip() != str(tenant_id or '').strip():
        raise PermissionError('cross-tenant external adapter credential denied')
    credential.validate()
    return credential


__all__ = [
    'CANON_EXTERNAL_ADAPTER_CREDENTIALS',
    'ExternalAdapterCredential',
    'assert_external_adapter_credential',
]
