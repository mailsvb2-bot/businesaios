from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


CANON_KMS_PROVIDER_CONTRACT = True


@dataclass(frozen=True)
class KMSKeyHandle:
    provider_name: str
    key_id: str
    key_version: int
    algorithm: str
    exportable: bool


@dataclass(frozen=True)
class KMSProviderCapability:
    provider_name: str
    supports_signing: bool
    supports_encryption: bool
    supports_rotation: bool
    supports_hsm_backed_keys: bool


class KMSProvider(Protocol):
    def capability(self) -> KMSProviderCapability: ...

    def create_key(
        self,
        *,
        key_id: str,
        algorithm: str,
        exportable: bool = False,
    ) -> KMSKeyHandle: ...

    def get_active_key(self, *, key_id: str) -> KMSKeyHandle: ...


__all__ = [
    'CANON_KMS_PROVIDER_CONTRACT',
    'KMSKeyHandle',
    'KMSProvider',
    'KMSProviderCapability',
]
