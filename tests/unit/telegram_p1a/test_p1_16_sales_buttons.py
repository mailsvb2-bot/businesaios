"""P1-16: «Продажи» commands as buttons over the same sales_pipeline@v1 ops."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.policies.telegram.router import handle
from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline
from tests.unit.business_flows.conftest import FlowEffects, FlowStore
from tests.unit.telegram_p1a._support import TENANT, make_ctx, validate_proposal_binding

NOW = 1_700_000_000_000


def _cbs(markup):
    return [b["callback_data"] for row in markup["inline_keyboard"] for b in row]


@pytest.mark.parametrize("callback,op", [
    ("sales:menu", "list"), ("sales:leads", "list"), ("sales:due", "due"), ("sales:followups", "followup"),
    ("sales:handoffs", "handoffs"), ("sales:closed", "closed"),
])
def test_list_buttons_propose_the_command_op(callback, op):
    ctx = make_ctx(user_id="1001", callback_data=callback, callback_query_id="cb-1", roles=["owner"])
    action, payload = validate_proposal_binding(handle(ctx, default_price_rub=990), ctx)
    assert action == "sales_pipeline@v1" and payload["op"] == op and payload["tenant_id"] == TENANT


def test_section_sales_button_is_schema_valid_with_callback_ack():
    ctx = make_ctx(user_id="1001", callback_data="cp:section:sales", callback_query_id="cb-7", roles=["owner"])
    action, payload = validate_proposal_binding(handle(ctx, default_price_rub=990), ctx)
    assert action == "sales_pipeline@v1" and payload["callback_query_id"] == "cb-7"
    ctx = make_ctx(user_id="1001", callback_data="cp:section:ad-channels", callback_query_id="cb-8", roles=["owner"])
    assert validate_proposal_binding(handle(ctx, default_price_rub=990), ctx)[0] == "bookings@v1"


@pytest.mark.parametrize("role", ["operator", "marketer", None])
def test_staff_without_sales_rights_get_no_sales_data(role):
    ctx = make_ctx(user_id="2002", callback_data="sales:leads", roles=[role] if role else [])
    out = handle(ctx, default_price_rub=990)
    assert out.action == "send_message@v1" and "подтверждённая роль" in out.payload["text"]


def _session(op, lead="", expires=NOW + 60_000):
    return {"sales:input": {"op": op, "lead_id": lead, "expires_ms": expires}}


def test_add_lead_button_then_text_becomes_lead_add():
    ctx = make_ctx(user_id="1001", callback_data="sales:in:add", callback_query_id="cb-2", roles=["owner"],
                   timestamp_ms=NOW)
    action, payload = validate_proposal_binding(handle(ctx, default_price_rub=990), ctx)
    assert action == "set_user_setting@v1" and payload["key"] == "sales:input"
    assert payload["value"]["op"] == "add" and payload["value"]["expires_ms"] == NOW + 600_000
    assert "sales:cancel" in _cbs(payload["notify_reply_markup"])

    typed = make_ctx(user_id="1001", text="Анна | Instagram", roles=["owner"], settings=payload["value"] and
                     {"sales:input": payload["value"]}, timestamp_ms=NOW + 1000)
    action, payload = validate_proposal_binding(handle(typed, default_price_rub=990), typed)
    assert action == "sales_pipeline@v1"
    assert payload["op"] == "add" and payload["arg"] == "Анна | Instagram" and payload["input_session"] is True


@pytest.mark.parametrize("op,text,arg", [
    ("note", "перезвонить после обеда", "lead_0123456789abcdef | перезвонить после обеда"),
    ("next", "2027-01-20 10:00 | позвонить", "lead_0123456789abcdef | 2027-01-20 10:00 | позвонить"),
    ("assign", "4002 лишнее", "lead_0123456789abcdef 4002"),
])
def test_lead_input_session_builds_the_command_argument(op, text, arg):
    ctx = make_ctx(user_id="1001", text=text, roles=["owner"], settings=_session(op, "lead_0123456789abcdef"),
                   timestamp_ms=NOW)
    action, payload = validate_proposal_binding(handle(ctx, default_price_rub=990), ctx)
    assert (action, payload["op"], payload["arg"]) == ("sales_pipeline@v1", op, arg)


def test_expired_forged_or_foreign_session_is_ignored():
    for settings in (_session("note", "lead_0123456789abcdef", expires=NOW - 1), _session("note", "../x"),
                     _session("refund", "lead_0123456789abcdef")):
        ctx = make_ctx(user_id="1001", text="текст", roles=["owner"], settings=settings, timestamp_ms=NOW)
        out = handle(ctx, default_price_rub=990)
        assert not (out.action == "sales_pipeline@v1" and out.payload.get("input_session"))
    guest = make_ctx(user_id="3003", text="текст", settings=_session("add"), timestamp_ms=NOW)
    out = handle(guest, default_price_rub=990)  # plain text stays a customer message (P0-9), never lead_add
    assert out.payload.get("op") != "add" and not out.payload.get("input_session")


def test_cancel_clears_the_session():
    ctx = make_ctx(user_id="1001", text="отмена", roles=["owner"], settings=_session("add"), timestamp_ms=NOW)
    action, payload = validate_proposal_binding(handle(ctx, default_price_rub=990), ctx)
    assert action == "set_user_setting@v1" and payload["value"] == {}


class _Effects(FlowEffects):
    def __init__(self, store):
        super().__init__(store)
        self.settings = []

    def set_user_setting(self, **kw):
        self.settings.append(kw)
        return {"ok": True}


def test_executor_runs_the_op_clears_session_and_list_has_buttons():
    store = FlowStore()
    effects = _Effects(store)
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d", correlation_id="c"))
    base = {"tenant_id": "t1", "user_id": "u1"}
    handle_sales_pipeline({**base, "op": "add", "arg": "Анна | Instagram", "input_session": True}, effects, env,
                          event_store=store, now_ms=NOW)
    assert effects.settings == [{"decision_id": "d", "correlation_id": "c", "tenant_id": "t1", "user_id": "u1",
                                 "key": "sales:input", "value": {}}]
    assert "Лид добавлен" in effects.sent[-1]["text"]
    lead_id = store.events[-1]["payload"]["lead_id"]
    handle_sales_pipeline({**base, "op": "note", "arg": f"{lead_id} | важный клиент"}, effects, env,
                          event_store=store, now_ms=NOW)
    assert "Заметка сохранена" in effects.sent[-1]["text"] and len(effects.settings) == 1
    handle_sales_pipeline({**base, "op": "list"}, effects, env, event_store=store, now_ms=NOW)
    cbs = _cbs(effects.sent[-1]["reply_markup"])
    assert {"sales:leads", "sales:in:add", "sales:due", "sales:followups", "cpm:sales"} <= set(cbs)
    assert all(len(c.encode()) <= 64 for c in cbs)
