from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from functools import partial

import pytest

from application.business_flows import external_products as xp
from runtime.handler_impl.domains.business_flow_ops import handle_business_admin

NOW = 1_800_000_000_000
SECRET = "s" * 40


def _sig(body: bytes, ts: int, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), str(ts).encode() + b"." + body, hashlib.sha256).hexdigest()


def _event(**kw) -> bytes:
    e = {"version": 1, "event_id": "e1", "type": "order_paid", "occurred_at": "2027-01-01T10:00:00Z",
         "customer_ref": "u-7", "amount_minor": 1500, "currency": "RUB"}  # fmt: skip
    return json.dumps({**e, **kw}).encode()


def test_signature_rules() -> None:
    now = datetime.fromtimestamp(NOW / 1000, UTC)
    ts, body = NOW // 1000, _event()
    xp.verify_signature(secret=SECRET, timestamp_header=str(ts), signature_header=_sig(body, ts), body=body, now=now)
    for kw, code in [
        ({"secret": "short"}, "secret_invalid"),
        ({"timestamp_header": "x"}, "timestamp_invalid"),
        ({"timestamp_header": str(ts - 301)}, "timestamp_expired"),
        ({"signature_header": "sha256=" + "0" * 64}, "signature_invalid"),
    ]:
        args = {"secret": SECRET, "timestamp_header": str(ts), "signature_header": _sig(body, ts), "body": body, **kw}
        with pytest.raises(xp.SignatureError, match=code):
            xp.verify_signature(now=now, **args)
    big = b"x" * (xp.MAX_BODY_BYTES + 1)
    with pytest.raises(xp.SignatureError, match="too_large"):
        xp.verify_signature(secret=SECRET, timestamp_header=str(ts), signature_header=_sig(big, ts), body=big, now=now)


def test_parse_strict_v1() -> None:
    assert xp.parse_event(_event())["money"] == {"amount_minor": 1500, "currency": "RUB"}
    for bad in [_event(version=2), _event(extra=1), _event(type="x"), _event(amount_minor=-1),
                _event(occurred_at="2027-01-01T10:00:00"), b"[]"]:  # fmt: skip
        with pytest.raises(ValueError):
            xp.parse_event(bad)


def test_lifecycle_and_webhook_via_handler(flow, monkeypatch) -> None:
    run = partial(flow.run, partial(handle_business_admin, now_ms=NOW))
    assert "ссылка на секрет" in run(op="xp_add", arg="crm " + SECRET)[1]  # raw secret refused
    _, text = run(op="xp_add", arg="crm env:XP_CRM_SECRET Моя CRM")
    cid = text.split()[2]
    assert "недоступен" in run(op="xp_activate", arg=cid)[1]
    monkeypatch.setenv("XP_CRM_SECRET", "short")
    assert "32 байт" in run(op="xp_activate", arg=cid)[1]
    monkeypatch.setenv("XP_CRM_SECRET", SECRET)
    assert "активирован" in run(op="xp_activate", arg=cid)[1]
    run(op="xp_bind", arg=f"{cid} u-7 cust-1")
    ts, body = NOW // 1000, _event()
    hdr = {"X-Businesaios-Timestamp": str(ts), "X-Businesaios-Signature": _sig(body, ts)}
    _, t = run(op="xp_ingest", connector_id=cid, raw_body=body.decode(), headers=hdr)
    assert t.startswith("accepted:")
    fact = flow.store.events[-1]["payload"]
    assert fact["customer_id"] == "cust-1" and SECRET not in json.dumps(fact)
    assert run(op="xp_ingest", connector_id=cid, raw_body=body.decode(), headers=hdr)[1].startswith("duplicate:")
    bad = {**hdr, "X-Businesaios-Signature": "sha256=" + "0" * 64}
    assert "signature_invalid" in run(op="xp_ingest", connector_id=cid, raw_body=body.decode(), headers=bad)[1]
    run(op="xp_feedback", arg=f"{t.split(':')[1]} useful")
    assert "useful_feedback: 1" in run(op="xp_value")[1]
    run(op="xp_disable", arg=cid)
    assert "inactive" in run(op="xp_ingest", connector_id=cid, raw_body=body.decode(), headers=hdr)[1]
