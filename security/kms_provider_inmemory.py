from __future__ import annotations

import threading
from dataclasses import dataclass

from security.kms_provider_contract import KMSKeyHandle, KMSProviderCapability


CANON_INMEMORY_KMS_PROVIDER = True


@dataclass(frozen=True)
class _StoredKMSKey:
    key_id: str
    key_version: int
    algorithm: str
    exportable: bool


class InMemoryKMSProvider:
    """Reference KMS/HSM-ready provider for tests and local governance wiring."""

    def __init__(self, *, provider_name: str = 'inmemory-kms', hsm_backed: bool = False) -> None:
        self._provider_name = str(provider_name)
        self._hsm_backed = bool(hsm_backed)
        self._keys: dict[str, list[_StoredKMSKey]] = {}
        self._lock = threading.RLock()

    def capability(self) -> KMSProviderCapability:
        return KMSProviderCapability(
            provider_name=self._provider_name,
            supports_signing=True,
            supports_encryption=True,
            supports_rotation=True,
            supports_hsm_backed_keys=self._hsm_backed,
        )

    def create_key(self, *, key_id: str, algorithm: str, exportable: bool = False, credential_ref: str | None = None) -> KMSKeyHandle:
        _ = credential_ref
        resolved_key_id = str(key_id).strip()
        resolved_algorithm = str(algorithm).strip()
        if not resolved_key_id:
            raise ValueError('key_id is required')
        if not resolved_algorithm:
            raise ValueError('algorithm is required')
        with self._lock:
            versions = self._keys.setdefault(resolved_key_id, [])
            version = len(versions) + 1
            stored = _StoredKMSKey(
                key_id=resolved_key_id,
                key_version=version,
                algorithm=resolved_algorithm,
                exportable=bool(exportable),
            )
            versions.append(stored)
        return KMSKeyHandle(
            provider_name=self._provider_name,
            key_id=stored.key_id,
            key_version=stored.key_version,
            algorithm=stored.algorithm,
            exportable=stored.exportable,
        )

    def get_active_key(self, *, key_id: str, credential_ref: str | None = None) -> KMSKeyHandle:
        _ = credential_ref
        resolved_key_id = str(key_id).strip()
        with self._lock:
            versions = self._keys.get(resolved_key_id)
            if not versions:
                self.create_key(key_id=resolved_key_id, algorithm='aes256_gcm', exportable=False, credential_ref=credential_ref)
                versions = self._keys.get(resolved_key_id)
            if not versions:
                raise KeyError(f'unknown kms key_id: {resolved_key_id}')
            stored = versions[-1]
        return KMSKeyHandle(
            provider_name=self._provider_name,
            key_id=stored.key_id,
            key_version=stored.key_version,
            algorithm=stored.algorithm,
            exportable=stored.exportable,
        )


__all__ = [
    'CANON_INMEMORY_KMS_PROVIDER',
    'InMemoryKMSProvider',
]
