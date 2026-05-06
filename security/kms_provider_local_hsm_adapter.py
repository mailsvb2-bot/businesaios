from __future__ import annotations

from security.kms_provider_contract import KMSKeyHandle, KMSProviderCapability
from security.kms_provider_sqlite import SQLiteKMSProvider


CANON_KMS_PROVIDER_LOCAL_HSM_ADAPTER = True


class LocalHSMKMSAdapter:
    """Local durable HSM-shaped adapter.

    This is not a cloud HSM claim. It is an explicit owner-surface that marks a
    locally isolated provider as HSM-backed for stricter capability-aware routing
    and tests without inventing a shadow crypto plane.
    """

    def __init__(self, db_path: str, *, provider_name: str = 'local-hsm') -> None:
        self._provider = SQLiteKMSProvider(db_path, provider_name=provider_name, hsm_backed=True)

    def capability(self) -> KMSProviderCapability:
        return self._provider.capability()

    def create_key(self, *, key_id: str, algorithm: str, exportable: bool = False) -> KMSKeyHandle:
        if exportable:
            raise ValueError('local hsm adapter forbids exportable keys')
        return self._provider.create_key(key_id=key_id, algorithm=algorithm, exportable=False)

    def get_active_key(self, *, key_id: str) -> KMSKeyHandle:
        return self._provider.get_active_key(key_id=key_id)


__all__ = [
    'CANON_KMS_PROVIDER_LOCAL_HSM_ADAPTER',
    'LocalHSMKMSAdapter',
]
