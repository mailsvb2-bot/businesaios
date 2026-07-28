from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config.env_flags import env_str


CANON_KEY_ENVELOPE = True
_KEY_ENVELOPE_MAGIC = b"BAIOS-KE2:"
_REJECTED_INTERMEDIATE_MAGIC = b"BAIOS-KE1:"
_NONCE_BYTES = 12
_MINIMUM_CIPHERTEXT_BYTES = 17  # one byte of key material plus the 128-bit GCM tag


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
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = AESGCM(load_key_envelope_master_key()).encrypt(
        nonce,
        plaintext,
        _aad(
            key_id=key_id,
            purpose=purpose,
            tenant_id=tenant_id,
            connector_id=connector_id,
        ),
    )
    return base64.b64encode(_KEY_ENVELOPE_MAGIC + nonce + ciphertext).decode("ascii")


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
    if payload.startswith(_REJECTED_INTERMEDIATE_MAGIC):
        raise RuntimeError(
            "BAIOS-KE1 key envelopes are unsupported; restore the pre-upgrade backup and rotate keys through the approved migration command"
        )
    if not payload.startswith(_KEY_ENVELOPE_MAGIC):
        raise RuntimeError("plaintext or unknown key material is forbidden; run the approved key-provider migration")
    body = payload[len(_KEY_ENVELOPE_MAGIC) :]
    if len(body) < _NONCE_BYTES + _MINIMUM_CIPHERTEXT_BYTES:
        raise RuntimeError("invalid key envelope length")
    nonce, ciphertext = body[:_NONCE_BYTES], body[_NONCE_BYTES:]
    try:
        return AESGCM(load_key_envelope_master_key()).decrypt(
            nonce,
            ciphertext,
            _aad(
                key_id=key_id,
                purpose=purpose,
                tenant_id=tenant_id,
                connector_id=connector_id,
            ),
        )
    except InvalidTag as exc:
        raise RuntimeError("key envelope integrity check failed") from exc


__all__ = [
    "CANON_KEY_ENVELOPE",
    "key_envelope_master_key_path",
    "load_key_envelope_master_key",
    "unwrap_key_material",
    "wrap_key_material",
]
