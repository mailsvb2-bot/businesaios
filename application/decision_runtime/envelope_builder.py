from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from core.ai.decision import Decision, DecisionEnvelope
from kernel.decision_crypto import signed_envelope_from_decision
from core.utils.canonical import sha256_hex


@dataclass(frozen=True)
class TaggedPayload:
    payload: dict[str, Any]
    product_id: str | None
    domain: str | None
    product_version: str | None


@dataclass(frozen=True)
class BuiltEnvelope:
    decision: Decision
    envelope: DecisionEnvelope
    payload_hash: str
    state_bytes: bytes


def bind_product_metadata(*, payload: dict[str, Any] | None, product_id: str | None, domain: str | None, product_version: str | None) -> TaggedPayload:
    bound = dict(payload or {})
    if product_id is not None:
        bound.setdefault("product_id", product_id)
    if domain is not None:
        bound.setdefault("domain", domain)
    if product_version is not None:
        bound.setdefault("product_version", product_version)
    return TaggedPayload(payload=bound, product_id=product_id, domain=domain, product_version=product_version)


def build_decision_envelope(*, state: Any, action: str, payload: dict[str, Any], policy_id: str, keyring: Any, issuer_id: str, ttl_ms: int, action_schema_version: int, envelope_version: int) -> BuiltEnvelope:
    state_bytes = state.canonical_bytes()
    state_hash = sha256_hex(state_bytes)
    snapshot_id = str(uuid.uuid4())
    issued_at_ms = int(time.time() * 1000)
    decision_id = str(uuid.uuid4())
    correlation_id = decision_id
    bound_payload = dict(payload or {})
    if action != "noop@v1":
        bound_payload.setdefault("idempotency_key", f"decision:{decision_id}")
    state_schema_version = int(getattr(state, "schema_version", 1) or 1)
    decision = Decision(
        decision_id=decision_id,
        issuer_id=issuer_id,
        issued_at_ms=issued_at_ms,
        expires_at_ms=issued_at_ms + int(ttl_ms),
        policy_id=policy_id,
        action=action,
        payload=bound_payload,
        snapshot_id=snapshot_id,
        state_hash=state_hash,
        correlation_id=correlation_id,
        state_schema_version=state_schema_version,
        action_schema_version=int(action_schema_version),
        envelope_version=int(envelope_version),
    )
    env = signed_envelope_from_decision(decision=decision, keyring=keyring)
    ph = env.payload_hash
    return BuiltEnvelope(decision=decision, envelope=env, payload_hash=ph, state_bytes=state_bytes)
