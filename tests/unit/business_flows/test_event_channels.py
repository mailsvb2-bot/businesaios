from __future__ import annotations

import re
from functools import partial

import pytest

from application.business_flows import bookings as bk
from application.business_flows import event_channels as ec
from runtime.handler_impl.domains.business_flow_ops import handle_bookings

NOW = 1_800_000_000_000


def _run(flow, now=NOW, **kw):
    return partial(flow.run, partial(handle_bookings, now_ms=now))(**kw)


def test_issue_consume_once_platform_bound_digest_only(flow) -> None:
    _run(flow, op="add_slot", arg="2027-01-20 15:00 Встреча")
    _run(flow, op="book", arg="1")
    _, text = _run(flow, op="link_channels", arg="1 vk")
    tokens = dict(re.findall(r"(\w+): /start ecv_(\S+)", text))
    assert set(tokens) == {"telegram", "vk", "max"}
    fact = flow.store.events[-1]["payload"]
    assert tokens["telegram"] not in str(fact) and all(len(x["digest"]) == 64 for x in fact["links"])
    assert "Не получилось" in _run(flow, op="channel_verify", arg="ecv_" + tokens["vk"])[1]  # telegram vs vk
    out, text = _run(flow, op="channel_verify", arg="/start ecv_" + tokens["telegram"])
    assert "подтверждён" in text and "Согласие" not in text
    assert "already consumed" in _run(flow, op="channel_verify", arg="ecv_" + tokens["telegram"])[1]
    _, text = _run(flow, op="channel_verify", arg="ecv_" + tokens["vk"], platform="vk", user_id="vk:42")
    assert "Согласие на рекламные" in text


def test_expired_and_foreign_booking() -> None:
    s = bk.Slot("s", "T", NOW + 10**7, 60, status="booked", customer_id="c")
    with pytest.raises(ec.LinkRejected):
        ec.issue(s, customer_id="other", now_ms=NOW)
    toks, fact = ec.issue(s, customer_id="c", now_ms=NOW, ttl_seconds=10)
    with pytest.raises(ec.LinkRejected, match="expired"):
        ec.consume([fact], {"s": s}, token=toks["max"], platform="max", external_subject="m1", now_ms=NOW + 61_000)
    with pytest.raises(ValueError):
        ec.marketing_platforms(["email"])
    assert ec.extract_token("start ecv_abc") == "abc" and ec.extract_token("/start cpa_x") is None
