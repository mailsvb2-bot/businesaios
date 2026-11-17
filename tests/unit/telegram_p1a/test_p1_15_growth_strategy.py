"""P1-15: Growth Strategy generate / view / accept / reject from «ИИ и автопилот»."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.policies.telegram.router import handle
from tests.unit.telegram_p1a._support import BUSINESS, TENANT, decide, make_ctx


def _callbacks(markup):
    return [b.get("callback_data") for row in markup["inline_keyboard"] for b in row]


def test_ai_section_leads_to_growth_strategy():
    ctx = make_ctx(user_id="1001", callback_data="autopilot:menu", roles=["owner"])
    assert "growth:menu" in _callbacks(handle(ctx, default_price_rub=990).payload["reply_markup"])
    menu = handle(make_ctx(user_id="1001", callback_data="growth:menu", roles=["owner"]), default_price_rub=990)
    assert {"growth:generate", "growth:backlog", "autopilot:menu"} <= set(_callbacks(menu.payload["reply_markup"]))
    assert "Стратегия роста" in menu.payload["text"]


@pytest.mark.parametrize("callback,action", [
    ("growth:generate", "growth_strategy_generate@v1"),
    ("growth:backlog", "growth_strategy_backlog@v1"),
    ("growth:accept:7c9e6679-7425-40de-944b-e07fc1f90ae7", "growth_strategy_accept@v1"),
    ("growth:reject:7c9e6679-7425-40de-944b-e07fc1f90ae7", "growth_strategy_reject@v1"),
])
def test_growth_buttons_use_canonical_business_scope_without_snapshot(callback, action):
    ctx = make_ctx(user_id="1001", callback_data=callback, callback_query_id="cb-9", roles=["owner"])
    got, payload = decide(handle(ctx, default_price_rub=990), ctx)
    assert got == action
    assert payload["tenant_id"] == TENANT and payload["business_id"] == BUSINESS


def test_generate_idempotency_is_per_press_not_global():
    a = handle(make_ctx(user_id="1001", callback_data="growth:generate", callback_query_id="cb-1", roles=["owner"]),
               default_price_rub=990)
    b = handle(make_ctx(user_id="1001", callback_data="growth:generate", callback_query_id="cb-2", roles=["owner"]),
               default_price_rub=990)
    assert a.payload["idempotency_key"] != b.payload["idempotency_key"]


def test_unbound_business_and_guest_are_refused():
    unbound = make_ctx(user_id="1001", callback_data="growth:generate", roles=["owner"],
                       product={"product_id": "organization_platform"})
    assert "выбери бизнес" in handle(unbound, default_price_rub=990).payload["text"]
    guest = handle(make_ctx(user_id="3003", callback_data="growth:generate"), default_price_rub=990)
    assert guest.action == "send_message@v1" and "владельцу" in guest.payload["text"]


def test_backlog_renders_decided_items_without_buttons_and_empty_state():
    from runtime.handlers.growth_strategy_backlog import _render_backlog

    h = lambda i: SimpleNamespace(hypothesis_id=f"h{i}", title=f"T{i}", stage="s", channel="c", metric="m", horizon_days=7)
    text, markup = _render_backlog([(h(1), None, "new"), (h(2), None, "accepted")])
    cbs = _callbacks(markup)
    assert "growth:accept:h1" in cbs and "growth:accept:h2" not in cbs
    text, markup = _render_backlog([])
    assert "Гипотез пока нет" in text and _callbacks(markup) == ["growth:menu"]
