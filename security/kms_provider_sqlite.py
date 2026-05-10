from __future__ import annotations

from security.kms_provider_contract import KMSKeyHandle, KMSProviderCapability
from runtime.platform.security_sqlite_stores import SQLiteKMSProviderBackend

CANON_SQLITE_KMS_PROVIDER = True


class SQLiteKMSProvider:
    """Security-facing SQLite KMS provider facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str, *, provider_name: str = 'sqlite-kms', hsm_backed: bool = False) -> None:
        self._provider_name = str(provider_name)
        self._hsm_backed = bool(hsm_backed)
        self._backend = SQLiteKMSProviderBackend(db_path)

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
        version = self._backend.create_key_row(
            key_id=resolved_key_id,
            algorithm=resolved_algorithm,
            exportable=bool(exportable),
        )
        return KMSKeyHandle(
            provider_name=self._provider_name,
            key_id=resolved_key_id,
            key_version=version,
            algorithm=resolved_algorithm,
            exportable=bool(exportable),
        )

    def get_active_key(self, *, key_id: str, credential_ref: str | None = None) -> KMSKeyHandle:
        _ = credential_ref
        resolved_key_id = str(key_id).strip()
        row = self._backend.get_active_key_row(key_id=resolved_key_id)
        if row is None:
            return self.create_key(key_id=resolved_key_id, algorithm='aes256_gcm', exportable=False, credential_ref=credential_ref)
        version, algorithm, exportable = row
        return KMSKeyHandle(
            provider_name=self._provider_name,
            key_id=resolved_key_id,
            key_version=version,
            algorithm=algorithm,
            exportable=exportable,
        )


__all__ = ['CANON_SQLITE_KMS_PROVIDER', 'SQLiteKMSProvider']
