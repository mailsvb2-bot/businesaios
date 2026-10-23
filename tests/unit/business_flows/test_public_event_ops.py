from __future__ import annotations

from functools import partial
from types import SimpleNamespace

import pytest

from contracts.customer import CustomerIdentityConflict
from runtime._internal.effects_domains.crm_projection import CrmProjectionEffectsMixin
from runtime.handler_impl.domains.business_flow_ops import handle_event_series

NOW = 1_800_000_000_000  # 2027-01-15


def _run(flow, op, arg):
    return flow.run(partial(handle_event_series, now_ms=NOW), op=op, arg=arg)[1]


def _slug(flow):
    return next(e["payload"]["slug"] for e in flow.store.events if e["payload"].get("step") == "pub_event_created")


def test_register_bind_links_verify(flow) -> None:
    calls = []

    def crm(**kw):
        calls.append(kw)
        return {"ok": True, "customer_id": "cus_1"}

    flow.effects.ensure_customer_identity = crm
    assert "Опубликовано" in _run(flow, "pub_create", "Вебинар | 2027-02-01 19:00 | Europe/Moscow")
    slug = _slug(flow)
    assert "Клиент привязан" in _run(flow, "pub_register", f"{slug} | Анна | anna@example.com")
    assert calls[0]["channel"] == "email" and calls[0]["decision_id"] == "d"
    assert "уже зарегистрированы" in _run(flow, "pub_register", f"{slug} | Анна | anna@example.com")
    text = _run(flow, "pub_links", slug)
    token = text.split("/event_verify ")[1].split()[0]
    assert "напоминания" in _run(flow, "pub_verify", token)
    assert "Ошибка" in _run(flow, "pub_verify", token) or "⚠" in _run(flow, "pub_verify", token)


def test_crm_unavailable_keeps_registration_and_blocks_links(flow) -> None:
    flow.effects.ensure_customer_identity = lambda **kw: {"ok": False, "reason": "crm_unavailable"}
    _run(flow, "pub_create", "Вебинар | 2027-02-01 19:00 | Europe/Moscow")
    slug = _slug(flow)
    assert "crm_unavailable" in _run(flow, "pub_register", f"{slug} | Анна | anna@example.com")
    assert any(e["payload"].get("step") == "pub_registration" for e in flow.store.events)
    assert "привязанной" in _run(flow, "pub_links", slug)


class _Log:
    def __init__(self):
        self.ev = []

    def emit(self, **kw):
        self.ev.append(kw)


class _Fx(CrmProjectionEffectsMixin):
    def __init__(self, reg):
        self.event_log, self.customer_registry = _Log(), reg


def _call(fx, **kw):
    return fx.ensure_customer_identity(decision_id="d", correlation_id="c", tenant_id="t", business_id="b",
                                       channel=kw.pop("channel", "email"), external_subject="a@x.ru", **kw)


def test_effect_requires_executor_and_handles_registry(monkeypatch) -> None:
    import runtime._internal.effects_domains.crm_projection as m
    monkeypatch.setattr(m, "assert_called_from_executor", lambda: None)
    assert _call(_Fx(None)) == {"ok": False, "reason": "crm_unavailable"}
    reg = SimpleNamespace(ensure_customer_identity=lambda **kw: SimpleNamespace(customer=SimpleNamespace(customer_id="c9")))
    fx = _Fx(reg)
    assert _call(fx) == {"ok": True, "customer_id": "c9"} and fx.event_log.ev[0]["event_type"] == "crm_identity_projected"

    def conflict(**kw):
        raise CustomerIdentityConflict("x")
    assert _call(_Fx(SimpleNamespace(attach_identity=conflict)), customer_id="c9")["reason"] == "identity_conflict"
    with pytest.raises(ValueError):
        _call(fx, channel="telegram")


def test_effect_blocked_outside_executor() -> None:
    with pytest.raises(Exception):
        _call(_Fx(None))


def test_ad_creatives_advisory_text() -> None:
    from runtime.handler_impl.domains.business_catalog_ops import _creatives_text

    text = _creatives_text("bookings ; A:j1:5000:200:60:10 ; B:j2:5000:200:10:2")
    assert "ready" in text and "Лидер: A" in text and "A 50%→60%" in text and "бюджет не меняется" in text
    assert "insufficient_data" in _creatives_text("A:j1:5000:5:1:0 ; B:j2:5000:5:1:0")
    with pytest.raises(ValueError):
        _creatives_text("A:j1")
