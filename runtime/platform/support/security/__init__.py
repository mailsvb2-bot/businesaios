from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .pii_redaction import PIIRedaction
from .secrets_provider import SecretsProvider

CANON_RUNTIME_SUPPORT_SECURITY_PACKAGE_OWNER = True
CANON_COMPAT_SHIM = True

class ArtifactSigning:
    def sign(self, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

class Auth:
    def authenticated(self, token: str | None) -> bool:
        return bool(token)

class Authz:
    def allowed(self, role: str, action: str) -> bool:
        if role == "admin":
            return True
        return action not in {"promote", "rollback", "override"}

class KeyRotation:
    def rotate(self, key_id: str) -> dict[str, str]:
        return {"rotated_key_id": key_id}

PERMISSIONS = {
    "admin": {"promote", "rollback", "override", "read", "write"},
    "viewer": {"read"},
    "operator": {"read", "write"},
}

@dataclass(frozen=True)
class ServiceIdentity:
    name: str

class SignatureVerification:
    def verify(self, payload: bytes, signature: str) -> bool:
        return hashlib.sha256(payload).hexdigest() == signature

class TransportSecurity:
    def secure(self, url: str) -> bool:
        return url.startswith("https://")

__all__ = [
    "ArtifactSigning",
    "Auth",
    "Authz",
    "KeyRotation",
    "PERMISSIONS",
    "PIIRedaction",
    "SecretsProvider",
    "ServiceIdentity",
    "SignatureVerification",
    "TransportSecurity",
]
