"""P1-20: take a lead into work with buttons — owner, accept, note, stage, next contact."""

from __future__ import annotations

from functools import partial

from core.policies.telegram.router import handle
from runtime.handler_impl.domains.business_flow_ops import handle_business_ops_summary, handle_sales_pipeline
from tests.unit.telegram_p1a._support import decide, make_ctx

NOW = 1_800_000_000_000


def _screen(flow, data):
    flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    return msg["text"], [b["callback_data"] for row in (msg.get("reply_markup") or {}).get("inline_keyboard", [])
                         for b in row]


def _press(flow, callback, *, settings=None, text=""):
    """Policy (as owner 'u1') -> DecisionCore binding -> executor, like the live path."""
    ctx = make_ctx(user_id="u1", callback_data=callback, text=text, roles=["owner"], settings=settings,
                   timestamp_ms=NOW)
    action, payload = decide(handle(ctx, default_price_rub=990), ctx)
    if action == "set_user_setting@v1":
        return action, payload
    assert action == "sales_pipeline@v1"
    body = {k: v for k, v in payload.items() if k not in {"tenant_id", "actor_id", "product_id", "business_id"}}

    flow.effects.set_user_setting = lambda **kw: {"ok": True}
    flow.run(partial(handle_sales_pipeline, now_ms=NOW), **body)
    return action, flow.effects.sent[-1]["text"]


def test_lead_card_buttons_take_note_next_contact_and_stage(flow):
    flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="add", arg="Анна | сайт")
    lead_id = flow.store.events[-1]["payload"]["lead_id"]
    text, cbs = _screen(flow, f"cpm:sales-lead:{lead_id}")
    assert {f"sales:do:take:{lead_id}", f"sales:in:note:{lead_id}", f"sales:in:next:{lead_id}",
            f"sales:in:assign:{lead_id}", f"cpm:sales-ev:{lead_id}:contact"} <= set(cbs)
    assert all(len(c.encode()) <= 64 for c in cbs)

    _, out = _press(flow, f"sales:do:take:{lead_id}")
    assert "ведёт u1" in out
    text, cbs = _screen(flow, f"cpm:sales-lead:{lead_id}")
    assert "Ответственный: u1" in text and f"sales:do:take:{lead_id}" not in cbs

    _, prompt = _press(flow, f"sales:in:note:{lead_id}")
    _, out = _press(flow, "", settings={"sales:input": prompt["value"]}, text="хочет рассрочку")
    assert "Заметка сохранена" in out
    _, prompt = _press(flow, f"sales:in:next:{lead_id}")
    _, out = _press(flow, "", settings={"sales:input": prompt["value"]}, text="2027-05-01 12:00 | перезвонить")
    assert "Следующий шаг записан" in out
    _screen(flow, f"cpm:sales-ev:{lead_id}:contact")
    text, _ = _screen(flow, f"cpm:sales-lead:{lead_id}")
    assert "на связи" in text and "перезвонить" in text


def test_take_cannot_assign_someone_else_and_closed_lead_has_no_work_buttons(flow):
    ctx = make_ctx(user_id="u1", callback_data="sales:do:take:lead_0123456789abcdef", roles=["owner"])
    _, payload = decide(handle(ctx, default_price_rub=990), ctx)
    assert payload["arg"] == "lead_0123456789abcdef u1"  # always the pressing user
    flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="add", arg="Борис | звонок")
    lead_id = flow.store.events[-1]["payload"]["lead_id"]
    _screen(flow, f"cpm:sales-ev:{lead_id}:declined")
    _, cbs = _screen(flow, f"cpm:sales-lead:{lead_id}")
    assert not any(c.startswith(("sales:do:take", "sales:in:")) for c in cbs)
