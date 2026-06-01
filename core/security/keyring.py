from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class KeyMeta:
    secret: bytes
    revoked: bool = False


class Keyring:
    """Signing keyring.

    - supports key rotation
    - supports revocation
    - enforces bytes secrets
    """

    def __init__(self, keys: dict[str, dict], active_kid: str):
        self._keys: dict[str, KeyMeta] = {}
        for kid, meta in (keys or {}).items():
            sec = meta.get("secret")
            if isinstance(sec, str):
                sec = sec.encode("utf-8")
            if not isinstance(sec, (bytes, bytearray)):
                raise TypeError("SECRET_MUST_BE_BYTES")
            self._keys[str(kid)] = KeyMeta(secret=bytes(sec), revoked=bool(meta.get("revoked", False)))
        if str(active_kid) not in self._keys:
            raise ValueError("ACTIVE_KID_NOT_IN_KEYRING")
        self._active = str(active_kid)

    def sign_key(self) -> tuple[str, bytes]:
        meta = self._keys[self._active]
        if meta.revoked:
            raise RuntimeError("ACTIVE_KEY_REVOKED")
        return self._active, meta.secret

    def verify_key(self, kid: str) -> bytes | None:
        meta = self._keys.get(str(kid))
        if not meta or meta.revoked:
            return None
        return meta.secret

    def revoke(self, kid: str) -> None:
        meta = self._keys.get(str(kid))
        if meta:
            meta.revoked = True

    def rotate(self, new_kid: str, new_secret: bytes) -> None:
        if isinstance(new_secret, str):
            new_secret = new_secret.encode("utf-8")
        self._keys[str(new_kid)] = KeyMeta(secret=bytes(new_secret), revoked=False)
        self._active = str(new_kid)

    def kids(self):
        return list(self._keys.keys())
