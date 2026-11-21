"""P1-13: the AI director reads the canonical growth read model, not an empty snapshot."""

from __future__ import annotations

from dataclasses import replace

from core.policies.telegram.router import handle
from interfaces.telegram.read_models import user_bundle
from tests.unit.telegram_p1a._support import TENANT, make_ctx, validate_proposal_binding


def _with_growth(ctx, growth):
    return replace(ctx, autopilot_dashboard={"growth": growth})


def test_read_model_hydrates_today_growth_kpi(monkeypatch):
    from core.growth import today_ledger

    seen = {}

    def fake_kpi(store, *, tenant_id, **_):
        seen["tenant"] = tenant_id
        return today_ledger.TodayGrowthKPI(leads=7, spend_minor=150000, revenue_minor=990000, profit_minor=840000)

    monkeypatch.setattr(today_ledger, "build_today_kpi", fake_kpi)
    bundle = user_bundle.load_user_bundle(event_store=object(), tenant_id=TENANT, user_id="1",
                                          event_warning=lambda **_: None)
    assert seen["tenant"] == TENANT
    assert bundle["autopilot_dashboard"]["growth"] == {
        "leads": 7, "spend_minor": 150000, "revenue_minor": 990000, "profit_minor": 840000}


def test_ceo_plan_shows_real_kpi_in_rubles():
    ctx = _with_growth(make_ctx(user_id="1001", callback_data="ceo:plan", roles=["owner"]),
                       {"leads": 7, "spend_minor": 150000, "revenue_minor": 990000, "profit_minor": 840000})
    action, payload = validate_proposal_binding(handle(ctx, default_price_rub=990), ctx)
    assert action == "ai_ceo_plan@v1"
    assert "лиды=7" in payload["text"] and "выручка=9900.00₽" in payload["text"]
    assert "прибыль=8400.00₽" in payload["text"]


def test_ceo_plan_without_read_model_is_honest_not_zero():
    ctx = make_ctx(user_id="1001", cmd="/ceo", roles=["owner"])
    _, payload = validate_proposal_binding(handle(ctx, default_price_rub=990), ctx)
    assert "данных о лидах и деньгах пока нет" in payload["text"] and "лиды=0" not in payload["text"]


def test_ceo_run_requires_owner_not_marketer():
    marketer = make_ctx(user_id="2002", callback_data="ceo:run", roles=["marketer"])
    out = handle(marketer, default_price_rub=990)
    assert out.action == "send_message@v1" and "подтверждённая роль" in out.payload["text"]
    owner = make_ctx(user_id="1001", callback_data="ceo:run", roles=["owner"])
    action, _ = validate_proposal_binding(handle(owner, default_price_rub=990), owner)
    # The canonical runtime cannot execute unapproved multi-step plans.
    assert action == "send_message@v1"
