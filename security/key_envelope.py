from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from config.env_flags import env_str


CANON_KEY_ENVELOPE = True
_KEY_ENVELOPE_MAGIC = b"BAIOS-KE1:"


def _is_production() -> bool:
    value = (env_str("APP_ENV", env_str("ENV", "dev")) or "dev").strip().lower()
    return value in {"prod", "production"}


def key_envelope_master_key_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".config" / "businesaios" / "key-provider-master.key"


def load_key_envelope_master_key() -> bytes:
    encoded = os.getenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", "").strip()
    if encoded:
        try:
            key = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise RuntimeError("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64 is invalid") from exc
        if len(key) != 32:
            raise RuntimeError("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64 must decode to exactly 32 bytes")
        return key

    if _is_production():
        raise RuntimeError("PRODUCTION_KEY_PROVIDER_MASTER_KEY_REQUIRED")

    path = key_envelope_master_key_path()
    if path.exists():
        key = path.read_bytes()
        if len(key) != 32:
            raise RuntimeError("development key-provider master key must be exactly 32 bytes")
        return key

    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(key)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _aad(*, key_id: str, purpose: str, tenant_id: str | None, connector_id: str | None) -> bytes:
    fields = (str(key_id), str(purpose), str(tenant_id or "-"), str(connector_id or "-"))
    if any("\n" in item or "\r" in item for item in fields):
        raise ValueError("key envelope scope fields must be single-line")
    return ("\n".join(fields) + "\n").encode("utf-8")


def _derive(master: bytes, *, label: bytes, nonce: bytes) -> bytes:
    return hmac.new(master, label + b":" + nonce, hashlib.sha256).digest()


def _keystream(key: bytes, *, nonce: bytes, size: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < size:
        output.extend(hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(output[:size])


def _xor(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise ValueError("key envelope operands must have equal length")
    return bytes(a ^ b for a, b in zip(left, right, strict=True))


def wrap_key_material(
    secret_bytes: bytes,
    *,
    key_id: str,
    purpose: str,
    tenant_id: str | None,
    connector_id: str | None,
) -> str:
    plaintext = bytes(secret_bytes)
    if not plaintext:
        raise ValueError("key material must not be empty")
    master = load_key_envelope_master_key()
    nonce = secrets.token_bytes(16)
    encryption_key = _derive(master, label=b"encryption", nonce=nonce)
    authentication_key = _derive(master, label=b"authentication", nonce=nonce)
    ciphertext = _xor(plaintext, _keystream(encryption_key, nonce=nonce, size=len(plaintext)))
    tag = hmac.new(
        authentication_key,
        _aad(key_id=key_id, purpose=purpose, tenant_id=tenant_id, connector_id=connector_id)
        + nonce
        + ciphertext,
        hashlib.sha256,
    ).digest()
    return base64.b64encode(_KEY_ENVELOPE_MAGIC + nonce + tag + ciphertext).decode("ascii")


def unwrap_key_material(
    wrapped: str,
    *,
    key_id: str,
    purpose: str,
    tenant_id: str | None,
    connector_id: str | None,
) -> bytes:
    try:
        payload = base64.b64decode(str(wrapped), validate=True)
    except Exception as exc:
        raise RuntimeError("invalid key envelope encoding") from exc
    if not payload.startswith(_KEY_ENVELOPE_MAGIC):
        raise RuntimeError("legacy plaintext key material is forbidden; run the explicit key migration")
    body = payload[len(_KEY_ENVELOPE_MAGIC) :]
    if len(body) < 49:
        raise RuntimeError("invalid key envelope length")
    nonce, tag, ciphertext = body[:16], body[16:48], body[48:]
    master = load_key_envelope_master_key()
    authentication_key = _derive(master, label=b"authentication", nonce=nonce)
    expected_tag = hmac.new(
        authentication_key,
        _aad(key_id=key_id, purpose=purpose, tenant_id=tenant_id, connector_id=connector_id)
        + nonce
        + ciphertext,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise RuntimeError("key envelope integrity check failed")
    encryption_key = _derive(master, label=b"encryption", nonce=nonce)
    return _xor(ciphertext, _keystream(encryption_key, nonce=nonce, size=len(ciphertext)))


__all__ = [
    "CANON_KEY_ENVELOPE",
    "key_envelope_master_key_path",
    "load_key_envelope_master_key",
    "unwrap_key_material",
    "wrap_key_material",
]
