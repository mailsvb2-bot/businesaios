"""P1-17: the customer card is the entry to sales (Telegram cockpit + web API/App.jsx)."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from types import SimpleNamespace

from runtime.handler_impl.domains.business_flow_ops import handle_business_ops_summary, handle_sales_pipeline

NOW = 1_800_000_000_000


def _screen(flow, data):
    flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    return msg["text"], [b["callback_data"] for row in (msg.get("reply_markup") or {}).get("inline_keyboard", [])
                         for b in row]


def test_inbound_customer_has_a_card_with_deals_owner_next_step_and_result(flow):
    run = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOW))
    run(op="inbound", arg="Сколько стоит?", reply="Я здесь.", user_id="cust7")
    text, cbs = _screen(flow, "cpm:customers")
    assert "cpm:customer:cust7" in cbs  # written-in customers are listed even without bookings
    text, cbs = _screen(flow, "cpm:customer:cust7")
    assert "Обращения и сделки" in text and "ответственный не назначен" in text and "Следующий шаг не задан" in text
    lead_cb = next(c for c in cbs if c.startswith("cpm:sales-lead:"))
    lead_id = lead_cb.rsplit(":", 1)[-1]
    run(op="assign", arg=f"{lead_id} u1")
    run(op="next", arg=f"{lead_id} | 2027-03-01 10:00 | позвонить")
    text, _ = _screen(flow, "cpm:customer:cust7")
    assert "ведёт u1" in text and "Следующий шаг: позвонить" in text
    text, cbs = _screen(flow, lead_cb)
    assert "Ответственный: u1" in text and "cpm:customer:cust7" in cbs
    _screen(flow, f"cpm:sales-ev:{lead_id}:paid")
    text, _ = _screen(flow, "cpm:customer:cust7")
    assert "Подтверждённый результат: оплата получена" in text


def test_web_customer_sales_is_identity_bound_and_flagged(flow, monkeypatch):
    import entrypoints.api.provider_admin_route_handlers as mod

    run = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOW))
    run(op="inbound", arg="Добрый день", reply="ok", user_id="cust7", business_id="b1")
    run(op="inbound", arg="Добрый день", reply="ok", user_id="stranger", business_id="b2")

    class Registry:
        def list_customers(self, *, tenant_id, business_id):
            return [SimpleNamespace(customer_id="c-1", status=SimpleNamespace(value="active"))]

        def get_customer(self, *, tenant_id, business_id, customer_id):
            return SimpleNamespace(identities=[])

    class Projector:
        def __init__(self, store):
            pass

        def get(self, **_):
            return SimpleNamespace(entries=[])

    monkeypatch.setattr(mod, "asdict", lambda obj: dict(vars(obj)))
    monkeypatch.setattr(mod, "CustomerTimelineProjector", Projector)
    handlers = mod.ProviderAdminRouteHandlers(customer_event_store=flow.store, customer_registry=Registry())
    monkeypatch.delenv("BAI_CUSTOMER_CARD_SALES_ENABLED", raising=False)
    assert "sales" not in handlers.get_business_customers(tenant_id="t1", business_id="b1", customer_id="c-1")

    monkeypatch.setenv("BAI_CUSTOMER_CARD_SALES_ENABLED", "1")
    out = handlers.get_business_customers(tenant_id="t1", business_id="b1", customer_id="c-1")
    assert out["sales"] == {"available": True, "leads": [], "source": "sales_pipeline@v1"}  # no identities -> nothing
    view = handlers._customer_sales(tenant_id="t1", business_id="b1", customer={"identities": [
        {"channel": "telegram", "external_subject": "cust7"}]})
    (lead,) = view["leads"]
    assert lead["stage_label"] == "на связи" and lead["owner"] == "" and lead["confirmed_result"] is None
    assert handlers._customer_sales(tenant_id="other", business_id="b1", customer={"identities": [
        {"channel": "telegram", "external_subject": "cust7"}]})["leads"] == []
    assert handlers._customer_sales(tenant_id="t1", business_id="b2", customer={"identities": [
        {"channel": "telegram", "external_subject": "cust7"}]})["leads"] == []


def test_app_renders_the_sales_block_only_when_the_api_provides_it():
    app = (Path(__file__).resolve().parents[3] / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "payload.sales?.available" in app and "Обращения и сделки" in app
    assert "Подтверждённый результат: оплата получена" in app


def test_scoped_owner_cockpit_never_exposes_other_business_sales(flow):
    from types import SimpleNamespace

    def run(user, business, index):
        env = SimpleNamespace(decision=SimpleNamespace(decision_id=f"d{index}", correlation_id=f"c{index}"))
        handle_sales_pipeline({"tenant_id": "t1", "user_id": user, "business_id": business,
                               "op": "inbound", "arg": "Нужна консультация", "reply": "ok"},
                              flow.effects, env, event_store=flow.store, now_ms=NOW)

    run("cust-a", "b1", 1)
    run("cust-b", "b2", 2)
    _, text_a = flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="cockpit",
                         arg="cpm:customers", business_id="b1")
    _, text_b = flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="cockpit",
                         arg="cpm:customers", business_id="b2")
    assert "cust-a" in text_a and "cust-b" not in text_a
    assert "cust-b" in text_b and "cust-a" not in text_b
