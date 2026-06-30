"""Signature/integrity checks for RuntimeGuard."""

from __future__ import annotations

from typing import Any
from kernel.decision_crypto import (
    assert_envelope_signature_surface,
    load_keyring_secret,
    verify_signed_material,
)
from runtime.enforcement import payload_hash

def verify_signature_and_integrity(*, env: Any, keyring: Any, schemas: Any, expected_issuer_id: str, supported_envelope_version: int, max_replay_ms: int, ttl_skew_ms: int, now_ms: int) -> None:
    assert_envelope_signature_surface(env)

    env_ver = int(getattr(env, "envelope_version", getattr(env.decision, "envelope_version", 1)))
    if env_ver != supported_envelope_version:
        raise RuntimeError("UNSUPPORTED_ENVELOPE_VERSION")

    if now_ms - int(env.decision.issued_at_ms) > max_replay_ms:
        raise RuntimeError("DECISION_EXPIRED")
    if now_ms > int(env.decision.expires_at_ms) + int(ttl_skew_ms):
        raise RuntimeError("TTL_EXPIRED")

    # Preserve public-api dependency for runtime boundary tests and fail-closed drift check.
    if payload_hash(env.decision.payload) != env.payload_hash:
        raise RuntimeError("PAYLOAD_TAMPERED")

    secret = load_keyring_secret(keyring=keyring, kid=env.kid)

    action_schema_version = int(getattr(env.decision, "action_schema_version", 0) or 0)
    if action_schema_version <= 0:
        raise RuntimeError("MISSING_ACTION_SCHEMA_VERSION")
    schemas.validate(env.decision.action, env.decision.payload, version=action_schema_version)

    state_schema_version = int(getattr(env.decision, "state_schema_version", 0) or 0)
    if state_schema_version <= 0:
        raise RuntimeError("MISSING_STATE_SCHEMA_VERSION")

    if not verify_signed_material(
        decision=env.decision,
        payload_hash_value=env.payload_hash,
        signature=env.signature,
        secret=secret,
        kid=env.kid,
    ):
        raise RuntimeError("BAD_SIGNATURE")

    if getattr(env.decision, "issuer_id", "") != expected_issuer_id:
        raise RuntimeError("BAD_ISSUER")


def verify_signature_gate(**kwargs) -> None:
    """Compatibility surface for guard split locks."""
    verify_signature_and_integrity(**kwargs)
