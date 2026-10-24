"""B2 regression: /event_links gives a user only the links of their own registration."""

from __future__ import annotations

import itertools
from functools import partial

from runtime.handler_impl.domains.business_flow_ops import handle_event_series

NOW = 1_800_000_000_000  # 2027-01-15


def _run(flow, uid, op, arg):
    return flow.run(partial(handle_event_series, now_ms=NOW), op=op, arg=arg, user_id=uid)[1]


def _issued(flow):
    return [e["payload"] for e in flow.store.events if e["payload"].get("step") == "channel_links_issued"]


def _setup(flow):
    ids = itertools.count(1)
    flow.effects.ensure_customer_identity = lambda **kw: {"ok": True, "customer_id": f"cus_{next(ids)}"}
    _run(flow, "owner", "pub_create", "Вебинар | 2027-02-01 19:00 | Europe/Moscow")
    slug = next(e["payload"]["slug"] for e in flow.store.events if e["payload"].get("step") == "pub_event_created")
    for uid, mail in (("u1", "a@example.com"), ("u2", "b@example.com")):
        assert "Клиент привязан" in _run(flow, uid, "pub_register", f"{slug} | Имя {uid} | {mail}")
    regs = {e["payload"]["registered_by"]: e["payload"]["registration_id"]
            for e in flow.store.events if e["payload"].get("step") == "pub_registration"}
    assert regs.keys() == {"telegram:u1", "telegram:u2"}
    return slug, regs


def test_each_registrant_gets_only_own_links(flow) -> None:
    slug, regs = _setup(flow)
    text1 = _run(flow, "u1", "pub_links", slug)
    text2 = _run(flow, "u2", "pub_links", slug)
    first, second = _issued(flow)
    assert first["registration_id"] == regs["telegram:u1"] and second["registration_id"] == regs["telegram:u2"]
    assert first["customer_id"] != second["customer_id"]
    # u1 was not served the last registration (the old regs[-1] behaviour)
    assert text1 != text2 and "/event_verify ecv_" in text1 and "/event_verify ecv_" in text2


def test_user_without_own_registration_gets_clear_refusal(flow) -> None:
    slug, _regs = _setup(flow)
    text = _run(flow, "u3", "pub_links", slug)
    assert "нет вашей привязанной регистрации" in text and f"/event_register {slug}" in text
    assert _issued(flow) == []


def test_registration_without_messenger_owner_is_not_served(flow) -> None:
    """Web/legacy registrations carry no messenger owner: no chat user may claim them."""
    slug, _regs = _setup(flow)
    for e in flow.store.events:
        e["payload"].pop("registered_by", None)
    assert "нет вашей привязанной регистрации" in _run(flow, "u1", "pub_links", slug)
    assert _issued(flow) == []
