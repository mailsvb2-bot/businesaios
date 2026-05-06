from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from security.kms_provider_contract import KMSKeyHandle, KMSProviderCapability

CANON_VAULT_TRANSIT_KMS_ADAPTER = True

@dataclass(frozen=True)
class VaultTransitConfig:
    mount_path: str = 'transit'
    provider_name: str = 'vault-transit'

    def validate(self) -> None:
        if not str(self.mount_path or '').strip():
            raise ValueError('mount_path is required')


class VaultTransitKMSAdapter:
    def __init__(self, config: VaultTransitConfig, *, create_key_fn: Callable[..., dict], get_active_key_fn: Callable[..., dict]) -> None:
        config.validate()
        self._config = config
        self._create_key_fn = create_key_fn
        self._get_active_key_fn = get_active_key_fn

    def capability(self) -> KMSProviderCapability:
        return KMSProviderCapability(provider_name=self._config.provider_name, supports_signing=True, supports_encryption=True, supports_rotation=True, supports_hsm_backed_keys=True)

    def create_key(self, *, key_id: str, algorithm: str, exportable: bool = False, credential_ref: str | None = None) -> KMSKeyHandle:
        response = dict(self._create_key_fn(mount_path=self._config.mount_path, key_id=str(key_id), algorithm=str(algorithm), exportable=bool(exportable), credential_ref=credential_ref))
        return KMSKeyHandle(provider_name=self._config.provider_name, key_id=str(response.get('key_id') or key_id), key_version=int(response.get('key_version') or 1), algorithm=str(response.get('algorithm') or algorithm), exportable=bool(response.get('exportable', exportable)))

    def get_active_key(self, *, key_id: str, credential_ref: str | None = None) -> KMSKeyHandle:
        response = dict(self._get_active_key_fn(mount_path=self._config.mount_path, key_id=str(key_id), credential_ref=credential_ref))
        return KMSKeyHandle(provider_name=self._config.provider_name, key_id=str(response.get('key_id') or key_id), key_version=int(response['key_version']), algorithm=str(response['algorithm']), exportable=bool(response.get('exportable', False)))

__all__ = ['CANON_VAULT_TRANSIT_KMS_ADAPTER', 'VaultTransitConfig', 'VaultTransitKMSAdapter']
