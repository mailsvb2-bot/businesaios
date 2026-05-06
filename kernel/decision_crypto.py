from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from core.utils.canonical import canonical_json_bytes, payload_hash

if TYPE_CHECKING:
    from core.ai.decision import Decision, DecisionEnvelope


CANON_DECISION_CRYPTO = True
DECISION_SIGNATURE_ALGORITHM = "hmac-sha256:v1"


@dataclass(frozen=True)
class SignedEnvelopeMaterial:
    payload_hash: str
    signature: str
    kid: str
    algorithm: str = DECISION_SIGNATURE_ALGORITHM


def _as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def canonical_signed_payload(
    *,
    decision: "Decision",
    payload_hash_value: str,
    kid: str,
) -> dict[str, Any]:
    """Canonical HMAC surface for DecisionEnvelope signing.

    IMPORTANT:
    Keep this bit-compatible with the existing runtime verification surface.
    """
    return {
        "envelope_version": _as_int(getattr(decision, "envelope_version", 1), default=1),
        "decision_id": str(getattr(decision, "decision_id", "") or ""),
        "issuer_id": str(getattr(decision, "issuer_id", "") or ""),
        "issued_at_ms": _as_int(getattr(decision, "issued_at_ms", 0)),
        "expires_at_ms": _as_int(getattr(decision, "expires_at_ms", 0)),
        "policy_id": str(getattr(decision, "policy_id", "") or ""),
        "action": str(getattr(decision, "action", "") or ""),
        "payload_hash": str(payload_hash_value or ""),
        "snapshot_id": str(getattr(decision, "snapshot_id", "") or ""),
        "state_hash": str(getattr(decision, "state_hash", "") or ""),
        "state_schema_version": _as_int(getattr(decision, "state_schema_version", 0)),
        "action_schema_version": _as_int(getattr(decision, "action_schema_version", 0)),
        "kid": str(kid or ""),
    }


def canonical_signed_bytes(
    *,
    decision: "Decision",
    payload_hash_value: str,
    kid: str,
) -> bytes:
    return canonical_json_bytes(
        canonical_signed_payload(
            decision=decision,
            payload_hash_value=payload_hash_value,
            kid=kid,
        )
    )


def sign_decision(*, decision: "Decision", secret: bytes, kid: str) -> SignedEnvelopeMaterial:
    ph = payload_hash(getattr(decision, "payload", {}) or {})
    signed_bytes = canonical_signed_bytes(
        decision=decision,
        payload_hash_value=ph,
        kid=kid,
    )
    signature = base64.b64encode(
        hmac.new(bytes(secret), signed_bytes, hashlib.sha256).digest()
    ).decode("ascii")
    return SignedEnvelopeMaterial(
        payload_hash=ph,
        signature=signature,
        kid=str(kid),
    )


def verify_signed_material(
    *,
    decision: "Decision",
    payload_hash_value: str,
    signature: str,
    secret: bytes,
    kid: str,
) -> bool:
    signed_bytes = canonical_signed_bytes(
        decision=decision,
        payload_hash_value=payload_hash_value,
        kid=kid,
    )
    expected_sig = base64.b64encode(
        hmac.new(bytes(secret), signed_bytes, hashlib.sha256).digest()
    ).decode("ascii")
    return hmac.compare_digest(str(expected_sig), str(signature or ""))


def envelope_has_required_signature_fields(env: "DecisionEnvelope") -> bool:
    return (
        bool(str(getattr(env, "payload_hash", "") or "").strip())
        and bool(str(getattr(env, "signature", "") or "").strip())
        and bool(str(getattr(env, "kid", "") or "").strip())
    )


def assert_envelope_signature_surface(env: "DecisionEnvelope") -> None:
    if not envelope_has_required_signature_fields(env):
        raise RuntimeError("ENVELOPE_NOT_SIGNED")
    computed_hash = payload_hash(getattr(env.decision, "payload", {}) or {})
    if not hmac.compare_digest(
        str(computed_hash),
        str(getattr(env, "payload_hash", "") or ""),
    ):
        raise RuntimeError("PAYLOAD_TAMPERED")


def signed_envelope_from_decision(*, decision: "Decision", keyring: Any) -> "DecisionEnvelope":
    from core.ai.decision import DecisionEnvelope

    kid, secret = keyring.sign_key()
    material = sign_decision(decision=decision, secret=secret, kid=kid)
    return DecisionEnvelope(
        decision=decision,
        payload_hash=material.payload_hash,
        signature=material.signature,
        kid=material.kid,
        envelope_version=_as_int(getattr(decision, "envelope_version", 1), default=1),
    )


def load_keyring_secret(*, keyring: Any, kid: str) -> bytes:
    secret = keyring.verify_key(str(kid))
    if not secret:
        raise RuntimeError("UNKNOWN_OR_REVOKED_KID")
    return bytes(secret)


def signed_material_for_archive(env: "DecisionEnvelope") -> Mapping[str, Any]:
    assert_envelope_signature_surface(env)
    return {
        "payload_hash": str(env.payload_hash),
        "signature": str(env.signature),
        "kid": str(env.kid),
        "signature_alg": DECISION_SIGNATURE_ALGORITHM,
    }
