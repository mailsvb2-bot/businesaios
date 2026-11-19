from __future__ import annotations

from application.business_flows import partners as pt
from runtime.handler_impl.domains.business_flow_ops import handle_partners


def _add(flow, name="Студия"):
    arg = f"{name} | wellness | 100 | existing | @studio"
    flow.run(handle_partners, op="add", arg=arg)
    return pt.parse_partner(arg)["partner_id"]


def _quote(flow, pid, amount, scope):
    flow.run(handle_partners, op="quote", arg=f"{pid} | {amount} | RUB | {scope}")
    return pt.create_quote(pid, str(amount), "RUB", scope)["quote_id"]


def _budget(flow, amount, currency="rub"):
    flow.store.events.append({
        "tenant_id": "t1", "user_id": "owner", "event_type": "business_admin@v1",
        "timestamp_ms": len(flow.store.events),
        "payload": {"step": "setting_set", "key": f"partner_budget_limit_minor.{currency}",
                    "value": str(amount)},
    })


def test_missing_budget_fails_closed_and_emits_no_approval(flow):
    pid = _add(flow)
    qid = _quote(flow, pid, 10000, "7 дней")
    _, response = flow.run(handle_partners, op="approve_quote", arg=qid)
    assert "partner_budget_not_configured" in response
    assert pt.quote_states([x["payload"] for x in flow.store.events])[qid]["status"] == "pending_owner_approval"


def test_budget_controls_approved_sum_and_repeated_clicks(flow):
    pid = _add(flow)
    _budget(flow, 15000)
    first = _quote(flow, pid, 10000, "Первый пост")
    second = _quote(flow, pid, 10000, "Второй пост")
    _, text = flow.run(handle_partners, op="approve_quote", arg=first)
    assert "Контрагенту не отправлено" in text
    approval = flow.effects.sent[-1]["track_payload"]
    assert approval["approved_by"] == "u1"
    assert approval["budget_limit_minor"] == 15000
    assert approval["quote_revision"] == first
    _, text = flow.run(handle_partners, op="approve_quote", arg=first)
    assert "уже учтено" in text
    _, text = flow.run(handle_partners, op="approve_quote", arg=second)
    assert "partner_budget_exceeded" in text
    assert pt.quote_states([x["payload"] for x in flow.store.events])[second]["status"] == "pending_owner_approval"


def test_bad_budget_setting_fails_closed(flow):
    pid = _add(flow)
    qid = _quote(flow, pid, 10000, "Публикация")
    _budget(flow, "not_money")
    _, text = flow.run(handle_partners, op="approve_quote", arg=qid)
    assert "partner_budget_invalid" in text


def test_rejection_never_requires_budget(flow):
    pid = _add(flow)
    qid = _quote(flow, pid, 10000, "Публикация")
    _, text = flow.run(handle_partners, op="reject_quote", arg=qid)
    assert "отклонено" in text
    assert pt.quote_states([x["payload"] for x in flow.store.events])[qid]["status"] == "rejected"


def test_quote_list_exposes_canonical_approve_callback(flow):
    pid = _add(flow)
    qid = _quote(flow, pid, 10000, "Публикация")
    flow.run(handle_partners, op="quotes")
    buttons = flow.effects.sent[-1]["reply_markup"]["inline_keyboard"]
    assert any(b["callback_data"] == "cp:partner:approve:" + qid for row in buttons for b in row)
    assert any(b["callback_data"] == "cp:partner:reject:" + qid for row in buttons for b in row)


def test_approval_callback_requires_owner_and_reuses_partners_action():
    from dataclasses import replace

    from core.policies.telegram.context import TelegramCtx
    from core.policies.telegram.router import handle

    class State:
        user_id = "owner-123"
        tenant_id = "t1"
        session = {}
        product = {"product_id": "organization_platform"}

    base = TelegramCtx(
        state=State(), text="", cmd=None, args="",
        callback_data="cp:partner:approve:pq_" + "a" * 24,
        callback_query_id="callback-77", settings={}, city="", moods=[],
        admin_metrics={}, is_admin=False, roles=[], perms=[], is_superadmin=False,
        realtime_state={}, pricing_suggestions={}, full_access=True,
        pay_status="none", selected_tariff={}, marketing_variants={},
        marketing_seed="1", marketing_bandit={},
    )
    denied = handle(base, default_price_rub=4900)
    assert denied.action != "partners@v1"
    assert "запрещён" in denied.payload["text"]
    allowed = handle(replace(base, is_admin=True), default_price_rub=4900)
    assert allowed.action == "partners@v1"
    assert allowed.payload["op"] == "approve_quote"
    assert allowed.payload["arg"] == "pq_" + "a" * 24
    assert allowed.payload["callback_query_id"] == "callback-77"
