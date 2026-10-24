from __future__ import annotations

from functools import partial

from runtime.handler_impl.domains.business_flow_ops import handle_business_ops_summary, handle_sales_pipeline

NOW = 1_800_000_000_000


def _screen(flow, data):
    flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    cbs = [b["callback_data"] for row in (msg.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]
    return msg["text"], cbs


def test_sales_screens_and_stage_buttons_reuse_reducer(flow) -> None:
    flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="add", arg="Анна | Instagram")
    text, cbs = _screen(flow, "cpm:sales")
    assert "Анна · новый" in text and "cpm:sales-recent" in cbs
    lead = next(c for c in cbs if c.startswith("cpm:sales-lead:"))
    assert all(len(c.encode()) <= 64 for c in cbs)
    text, cbs = _screen(flow, lead)
    lead_id = lead.split(":")[2]
    assert f"cpm:sales-ev:{lead_id}:contact" in cbs and cbs[-2:] == ["cpm:sales", "cpm:menu"]
    text, cbs = _screen(flow, f"cpm:sales-ev:{lead_id}:contact")
    assert "Анна: на связи" in text and f"cpm:sales-ev:{lead_id}:need" in cbs
    text, _ = _screen(flow, f"cpm:sales-ev:{lead_id}:checkout")  # skip refused by the shared reducer
    assert "Не получилось" in text
    _screen(flow, f"cpm:sales-ev:{lead_id}:handoff")
    text, cbs = _screen(flow, "cpm:sales")
    assert "cpm:sales-handoffs" in cbs
    text, cbs = _screen(flow, "cpm:sales-handoffs")
    assert "1. Анна" in text and f"cpm:sales-ev:{lead_id}:resume" in cbs
    _screen(flow, f"cpm:sales-ev:{lead_id}:paid")
    text, _ = _screen(flow, "cpm:sales-recent")
    assert "Анна · купил" in text
    text, _ = _screen(flow, f"cpm:sales-actions:{lead_id}")
    assert "закрыто" in text
    assert "неактуальна" in _screen(flow, "cpm:sales-lead:lead_nope")[0]
