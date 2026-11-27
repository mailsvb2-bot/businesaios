"""Review-level proof, source and privacy integration contracts."""
from __future__ import annotations

import base64
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from application.business_flows.external_products import PriceObservation, price_change
from interfaces.uiii.signals import MappingContext, SignalRejected, to_external_product_event, verify_signal

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)


def encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def fixture():
    key = Ed25519PrivateKey.generate()
    keys = {("issuer", "k1"): key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)}
    context = MappingContext(
        "issuer", "ba", "t", "b", "controller", "crm", "connection", "customer", frozenset({"attendance"}), True
    )
    payload = {
        "schema": "uiii.observation.v1", "issuer": "issuer", "audience": "ba",
        "scope": {"tenant_id": "t", "business_id": "b", "controller_id": "controller",
                  "purpose": "crm", "connection_id": "connection"},
        "signal_id": "s1", "revision": 1,
        "generated_at": NOW.isoformat(), "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "customer_ref": "customer", "rights": {"purpose": "crm", "status": "ALLOW"},
        "state": "active",
        "observation": {"kind": "attendance", "label": "Участие", "observed_at": NOW.isoformat(),
                        "fresh_until": None, "provenance_ref": "proof-1",
                        "quality": "source_verified", "limitations": []},
    }

    def sign(p=None, header=None):
        h = encode(json.dumps(header or {"alg": "EdDSA", "kid": "k1", "typ": "uiii.signal+jws"}).encode())
        body = encode(json.dumps(payload if p is None else p).encode())
        signature = encode(key.sign((h + "." + body).encode()))
        return h + "." + body + "." + signature

    return context, keys, payload, sign


def test_proof_to_strict_xp_and_revalidation_before_send():
    context, keys, _, sign = fixture()
    verified = verify_signal(sign(), context=context, keys=keys, now=NOW)
    body = to_external_product_event(verified, context=context, keys=keys, now=NOW)
    event = json.loads(body)
    assert event["type"] == "evidence" and event["event_id"] == "uiii:s1:r1"
    assert "business_id" not in event
    with pytest.raises(SignalRejected):
        to_external_product_event(verified, context=replace(context, data_use_allowed=False), keys=keys, now=NOW)
    with pytest.raises(SignalRejected):
        to_external_product_event(verified, context=context, keys={}, now=NOW)


@pytest.mark.parametrize("change", [
    {"schema": "wrong"}, {"revision": 0}, {"customer_ref": "foreign"},
    {"audience": "other"}, {"rights": {"purpose": "crm", "status": "DENY"}},
])
def test_invalid_semantics_are_rejected(change):
    context, keys, p, sign = fixture()
    with pytest.raises(SignalRejected):
        verify_signal(sign({**p, **change}), context=context, keys=keys, now=NOW)


def test_scope_time_key_and_tamper():
    context, keys, p, sign = fixture()
    for changed in (replace(context, business_id="other"), replace(context, purpose="ads"),
                    replace(context, revoked_signal_revisions=frozenset({("s1", 1)}))):
        with pytest.raises(SignalRejected):
            verify_signal(sign(), context=changed, keys=keys, now=NOW)
    with pytest.raises(SignalRejected):
        verify_signal(sign(), context=context, keys=keys, now=NOW + timedelta(hours=2))
    with pytest.raises(SignalRejected):
        verify_signal(sign(header={"alg": "none", "kid": "k1", "typ": "uiii.signal+jws"}),
                      context=context, keys=keys, now=NOW)
    segments = sign().split(".")
    segments[1] = encode(json.dumps({**p, "revision": 2}).encode())
    with pytest.raises(SignalRejected):
        verify_signal(".".join(segments), context=context, keys=keys, now=NOW)


def test_exact_price_and_unknown_stock():
    a = PriceObservation("variant", "RU", "piece", "RUB", "inc-tax",
                         Decimal("0.10"), NOW - timedelta(hours=1), "a", "provider")
    b = replace(a, amount=Decimal("0.30"), observed_at=NOW, evidence_ref="b")
    assert price_change(a, b, now=NOW, max_age_seconds=60)["delta"] == "0.20"
    assert price_change(a, replace(b, currency="USD"), now=NOW, max_age_seconds=60)["status"] == "NOT_COMPARABLE"
    assert price_change(a, b, now=NOW + timedelta(days=1), max_age_seconds=60)["status"] == "STALE"
    assert a.stock is None


def test_purpose_scoped_privacy_token():
    from interfaces.uiii.signals import purpose_token

    kw = dict(key=b"x" * 32, key_id="v1", tenant="t", business="b", controller="c", purpose="crm")
    token = purpose_token("same@example.org", **kw)
    assert token == purpose_token("same@example.org", **kw)
    assert token != purpose_token("same@example.org", **{**kw, "business": "other"})
    assert token != purpose_token("same@example.org", **{**kw, "purpose": "ads"})
    assert "same@example.org" not in token


@pytest.mark.parametrize("field,value", [
    ("kind", []), ("kind", {}), ("state", []), ("state", {}),
])
def test_invalid_signal_field_types_fail_closed(field, value):
    context, keys, p, sign = fixture()
    if field == "kind":
        p["observation"][field] = value
    else:
        p["state"] = value
    with pytest.raises(SignalRejected):
        verify_signal(sign(p), context=context, keys=keys, now=NOW)


@pytest.mark.parametrize("seconds", [-1, 0])
def test_active_signal_cannot_outlive_observation(seconds):
    context, keys, p, sign = fixture()
    p["observation"]["observed_at"] = (NOW - timedelta(hours=1)).isoformat()
    p["observation"]["fresh_until"] = (NOW + timedelta(seconds=seconds)).isoformat()
    with pytest.raises(SignalRejected, match="observation_stale"):
        verify_signal(sign(p), context=context, keys=keys, now=NOW)


def test_mapper_rechecks_freshness_and_delivers_retractions():
    context, keys, p, sign = fixture()
    p["observation"]["fresh_until"] = (NOW + timedelta(seconds=1)).isoformat()
    verified = verify_signal(sign(p), context=context, keys=keys, now=NOW)
    with pytest.raises(SignalRejected, match="observation_stale"):
        to_external_product_event(verified, context=context, keys=keys, now=NOW + timedelta(seconds=1))
    p["state"] = "retracted"
    withdrawn = verify_signal(sign(p), context=context, keys=keys, now=NOW + timedelta(seconds=2))
    body = to_external_product_event(withdrawn, context=context, keys=keys, now=NOW + timedelta(seconds=2))
    assert json.loads(body)["observation"]["state"] == "retracted"


@pytest.mark.parametrize("field,value", [
    ("label", ""), ("quality", {}), ("quality", ""), ("limitations", {}),
    ("limitations", ["x" * 201]), ("provenance_ref", 3),
])
def test_bad_parser_fields_have_stable_error(field, value):
    context, keys, p, sign = fixture()
    p["observation"][field] = value
    with pytest.raises(SignalRejected, match="observation_invalid"):
        verify_signal(sign(p), context=context, keys=keys, now=NOW)
