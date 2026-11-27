"""Verify a pinned Ed25519 JWS and map observations into existing XP v1 evidence.

This is a pure adapter. Keys, rights, permissions and customer identity must be
supplied by the canonical authorized host; no network, store or decision engine.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from application.business_flows.external_products import MAX_BODY_BYTES, OBS_QUALITY, parse_event


class SignalRejected(ValueError):
    """Stable rejection code; never include untrusted material."""


def _decode(value: str) -> bytes:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    if not isinstance(value, str) or not value or any(c not in alphabet for c in value):
        raise SignalRejected("invalid_base64url")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError):
        raise SignalRejected("invalid_base64url") from None
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode() != value:
        raise SignalRejected("noncanonical_base64url")
    return raw


def _unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise SignalRejected("duplicate_json_key")
        out[k] = v
    return out


def _json(raw: bytes) -> dict[str, Any]:
    try:
        result = json.loads(
            raw, object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(SignalRejected("invalid_number")),
        )
    except (ValueError, UnicodeError, RecursionError):
        raise SignalRejected("invalid_json") from None
    if not isinstance(result, dict):
        raise SignalRejected("object_required")
    return result


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 80:
        raise SignalRejected("timestamp_required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SignalRejected("timestamp_invalid") from None
    if result.tzinfo is None:
        raise SignalRejected("timestamp_timezone_required")
    return result.astimezone(UTC)


def _text(value: Any, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise SignalRejected("invalid_text")
    return value


@dataclass(frozen=True)
class MappingContext:
    """Trusted context from canonical tenant/business/customer binding, not the JWS."""
    issuer: str
    audience: str
    tenant_id: str
    business_id: str
    controller_id: str
    purpose: str
    connection_id: str
    customer_ref: str
    permitted_observation_kinds: frozenset[str]
    data_use_allowed: bool
    revoked_signal_revisions: frozenset[tuple[str, int]] = field(default_factory=frozenset)

    def __post_init__(self):
        for value in (
            self.issuer, self.audience, self.tenant_id, self.business_id,
            self.controller_id, self.purpose, self.connection_id, self.customer_ref,
        ):
            _text(value, 200)
        if type(self.data_use_allowed) is not bool:
            raise SignalRejected("invalid_data_use_context")


@dataclass(frozen=True)
class VerifiedSignal:
    payload_bytes: bytes
    payload_sha256: str
    key_id: str
    issuer: str
    compact_jws: str

    def payload(self) -> dict[str, Any]:
        if hashlib.sha256(self.payload_bytes).hexdigest() != self.payload_sha256:
            raise SignalRejected("proof_digest_mismatch")
        return _json(self.payload_bytes)


def verify_signal(
    compact_jws: str, *, context: MappingContext,
    keys: Mapping[tuple[str, str], bytes], now: datetime,
) -> VerifiedSignal:
    """Only pinned issuer/kid raw public keys; no x5u, jku, alg substitution."""
    if not isinstance(compact_jws, str) or len(compact_jws) > 96_000 or now.tzinfo is None:
        raise SignalRejected("invalid_proof_or_clock")
    try:
        protected, encoded, sig = compact_jws.split(".")
    except ValueError:
        raise SignalRejected("invalid_jws") from None
    header = _json(_decode(protected))
    if set(header) != {"alg", "kid", "typ"} or header.get("alg") != "EdDSA" or header.get("typ") != "uiii.signal+jws":
        raise SignalRejected("unsupported_jws_header")
    kid = _text(header.get("kid"), 120)
    key = keys.get((context.issuer, kid))
    if key is None:
        raise SignalRejected("unknown_or_revoked_key")
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(
            _decode(sig), (protected + "." + encoded).encode("ascii"),
        )
    except (ValueError, InvalidSignature):
        raise SignalRejected("signature_invalid") from None
    raw = _decode(encoded)
    if len(raw) > 64_000:
        raise SignalRejected("payload_too_large")
    payload = _json(raw)
    _validate(payload, context=context, now=now)
    return VerifiedSignal(raw, hashlib.sha256(raw).hexdigest(), kid, context.issuer, compact_jws)


def _validate(payload: dict[str, Any], *, context: MappingContext, now: datetime) -> None:
    allowed = {
        "schema", "issuer", "audience", "scope", "signal_id", "revision",
        "generated_at", "expires_at", "observation", "rights",
        "customer_ref", "state", "supersedes_external_event_id",
    }
    if set(payload) - allowed or payload.get("schema") != "uiii.observation.v1":
        raise SignalRejected("schema_incompatible")
    expected_scope = {
        "tenant_id": context.tenant_id, "business_id": context.business_id,
        "controller_id": context.controller_id, "purpose": context.purpose,
        "connection_id": context.connection_id,
    }
    if (
        payload.get("scope") != expected_scope
        or payload.get("issuer") != context.issuer
        or payload.get("audience") != context.audience
    ):
        raise SignalRejected("scope_mismatch")
    if payload.get("customer_ref") != context.customer_ref:
        raise SignalRejected("customer_binding_mismatch")
    sid = _text(payload.get("signal_id"), 160)
    rev = payload.get("revision")
    if type(rev) is not int or rev < 1:
        raise SignalRejected("revision_invalid")
    if (sid, rev) in context.revoked_signal_revisions:
        raise SignalRejected("signal_revoked")
    created, expires = _time(payload.get("generated_at")), _time(payload.get("expires_at"))
    if not created <= now < expires:
        raise SignalRejected("signal_not_current")
    if (
        context.data_use_allowed is not True
        or payload.get("rights") != {"purpose": context.purpose, "status": "ALLOW"}
    ):
        raise SignalRejected("data_use_denied")
    observation = payload.get("observation")
    if not isinstance(observation, dict) or set(observation) != {
        "kind", "label", "observed_at", "fresh_until",
        "provenance_ref", "quality", "limitations",
    }:
        raise SignalRejected("observation_schema_invalid")
    if not isinstance(observation["kind"], str) or observation["kind"] not in context.permitted_observation_kinds:
        raise SignalRejected("capability_denied")
    if _time(observation["observed_at"]) > now:
        raise SignalRejected("future_observation")
    if not isinstance(payload.get("state"), str) or payload["state"] not in {"active", "retracted"}:
        raise SignalRejected("invalid_state")
    if (
        not isinstance(observation["quality"], str)
        or observation["quality"] not in OBS_QUALITY
        or not isinstance(observation["limitations"], list)
    ):
        raise SignalRejected("observation_invalid")
    try:
        parse_event(json.dumps(_event(payload), ensure_ascii=False, allow_nan=False).encode())
    except (ValueError, TypeError, OverflowError):
        raise SignalRejected("observation_invalid") from None
    if (
        payload["state"] == "active" and observation["fresh_until"] is not None
        and now >= _time(observation["fresh_until"])
    ):
        raise SignalRejected("observation_stale")


def _event(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1, "type": "evidence",
        "event_id": f"uiii:{payload['signal_id']}:r{payload['revision']}",
        "occurred_at": payload["observation"]["observed_at"],
        "customer_ref": payload["customer_ref"],
        "observation": {
            "observation_key": payload["signal_id"],
            "revision": payload["revision"],
            "state": payload["state"],
            "supersedes_external_event_id": payload.get("supersedes_external_event_id"),
            **payload["observation"],
        },
    }


def to_external_product_event(
    signal: VerifiedSignal, *, context: MappingContext,
    keys: Mapping[tuple[str, str], bytes], now: datetime,
) -> bytes:
    """Recheck grant and proof at use time; never trust a cached verification."""
    checked = verify_signal(signal.compact_jws, context=context, keys=keys, now=now)
    if checked != signal:
        raise SignalRejected("verified_artifact_mismatch")
    event = _event(checked.payload())
    event["metadata"] = {
        "uiii_payload_sha256": signal.payload_sha256,
        "uiii_kid": signal.key_id,
        "uiii_issuer": signal.issuer,
        "mapper_version": "1",
    }
    body = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(body) > MAX_BODY_BYTES:
        raise SignalRejected("mapped_payload_too_large")
    return body


def xp_headers(body: bytes, *, secret: bytes, now: datetime) -> dict[str, str]:
    """HMAC envelope only; outbound delivery remains canonical execution effect."""
    if len(secret) < 32 or now.tzinfo is None:
        raise SignalRejected("invalid_secret_or_clock")
    timestamp = str(int(now.timestamp()))
    signature = hmac.new(secret, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"X-Businesaios-Timestamp": timestamp, "X-Businesaios-Signature": "sha256=" + signature}


def purpose_token(
    value: str, *, key: bytes, key_id: str, tenant: str, business: str, controller: str, purpose: str
) -> str:
    if len(key) < 32 or not all((value, key_id, tenant, business, controller, purpose)):
        raise ValueError("complete scope and >=256-bit key required")
    message = json.dumps(
        ["uiii-token-v1", tenant, business, controller, purpose, value],
        ensure_ascii=False, separators=(",", ":"),
    ).encode()
    return key_id + ":" + hmac.new(key, message, hashlib.sha256).hexdigest()


def lineage_event(*, run_id: str, job: str, namespace: str, at: str, datasets: list[Mapping[str, str]]) -> dict:
    """OpenLineage-shaped metadata; not an actual export transport or full PROV graph."""
    from datetime import datetime
    from uuid import UUID

    UUID(run_id)
    if datetime.fromisoformat(at.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("timezone required")
    if not job or not namespace or len(datasets) > 100:
        raise ValueError("bounded lineage context required")
    inputs = []
    for item in datasets:
        if set(item) != {"namespace", "name"} or not all(
            isinstance(v, str) and v and len(v) < 200 for v in item.values()
        ):
            raise ValueError("opaque dataset reference required")
        inputs.append(dict(item))
    return {
        "eventType": "COMPLETE",
        "eventTime": at,
        "run": {"runId": run_id},
        "job": {"namespace": namespace, "name": job},
        "inputs": inputs,
        "outputs": [],
        "producer": "urn:uiii:lineage:1",
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
    }
