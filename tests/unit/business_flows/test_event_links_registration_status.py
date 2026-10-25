"""M16 guard: /event_links serves only an active (status == "registered") registration of the caller."""

from __future__ import annotations

import itertools
from functools import partial

from runtime.handler_impl.domains.business_flow_ops import handle_event_series

NOW = 1_800_000_000_000  # 2027-01-15
REFUSAL = "нет вашей привязанной регистрации"


def _run(flow, uid, op, arg):
    return flow.run(partial(handle_event_series, now_ms=NOW), op=op, arg=arg, user_id=uid)[1]


def _issued(flow):
    return [e["payload"] for e in flow.store.events if e["payload"].get("step") == "channel_links_issued"]


def _registered(flow):
    ids = itertools.count(1)
    flow.effects.ensure_customer_identity = lambda **kw: {"ok": True, "customer_id": f"cus_{next(ids)}"}
    _run(flow, "owner", "pub_create", "Вебинар | 2027-02-01 19:00 | Europe/Moscow")
    slug = next(e["payload"]["slug"] for e in flow.store.events if e["payload"].get("step") == "pub_event_created")
    assert "Клиент привязан" in _run(flow, "u1", "pub_register", f"{slug} | Имя | a@example.com")
    reg = next(e for e in flow.store.events if e["payload"].get("step") == "pub_registration")
    return slug, reg


def _cancel(flow, reg) -> None:
    flow.store.events.append({
        **{k: v for k, v in reg.items() if k != "payload"},
        "timestamp_ms": len(flow.store.events),
        "payload": {"step": "pub_registration_cancelled", "registration_id": reg["payload"]["registration_id"],
                    "event_id": reg["payload"]["event_id"]},
    })


def test_active_registration_gets_links(flow) -> None:
    slug, _reg = _registered(flow)
    assert "/event_verify ecv_" in _run(flow, "u1", "pub_links", slug)
    assert len(_issued(flow)) == 1


def test_cancelled_registration_gets_no_links(flow) -> None:
    slug, reg = _registered(flow)
    _cancel(flow, reg)
    text = _run(flow, "u1", "pub_links", slug)
    assert REFUSAL in text and "/event_verify" not in text
    assert _issued(flow) == []
