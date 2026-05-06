from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


CANON_ENCRYPTION_POLICY = True


class EncryptionAlgorithm(str, Enum):
    SEALED_BOX_V1 = 'sealed_box_v1'
    XOR_DEMO_ONLY = 'xor_demo_only'
    AES256_GCM = 'aes256_gcm'
    FERNET = 'fernet'


@dataclass(frozen=True)
class EncryptionPolicy:
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.SEALED_BOX_V1
    require_encryption_at_rest: bool = True
    require_key_rotation: bool = True
    max_plaintext_bytes: int = 65536
    require_tenant_binding: bool = True
    extra_context_fields: tuple[str, ...] = ('tenant_id', 'secret_name', 'connector_id')
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if int(self.max_plaintext_bytes) <= 0:
            raise ValueError('max_plaintext_bytes must be > 0')

    def allows_plaintext_storage(self) -> bool:
        return False

    def validate_plaintext_size(self, plaintext: bytes) -> None:
        self.validate()
        if len(plaintext) > int(self.max_plaintext_bytes):
            raise ValueError('plaintext exceeds max_plaintext_bytes')

    def require_external_crypto_adapter(self) -> bool:
        return self.algorithm in {EncryptionAlgorithm.AES256_GCM, EncryptionAlgorithm.FERNET}


__all__ = [
    'CANON_ENCRYPTION_POLICY',
    'EncryptionAlgorithm',
    'EncryptionPolicy',
]
