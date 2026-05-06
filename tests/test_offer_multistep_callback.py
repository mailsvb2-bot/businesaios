from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.router import handle


class _DummyState:
    def __init__(self) -> None:
        self.user_id = "u1"
        self.tenant_id = "tenantA"
        self.product = {"product_id": "organization_platform", "domain": "organization_platform"}


def test_offer_accept_callback_returns_execute_plan_with_payment_step():
    ctx = TelegramCtx(
        state=_DummyState(),
        text="",
        cmd=None,
        args="",
        callback_data="offer:accept:launch",
        callback_query_id="cbq1",
        settings={},
        city="",
        moods=[],
        admin_metrics={},
        is_admin=False,
        roles=[],
        perms=[],
        is_superadmin=False,
        realtime_state={},
        pricing_suggestions={},
        full_access=False,
        pay_status="none",
        selected_tariff={"price_rub": 1234},
        marketing_variants={},
        marketing_seed="1",
        marketing_bandit={},
    )

    out = handle(ctx, default_price_rub=4900)
    assert isinstance(out, dict)
    assert out.get("action") == "execute_plan@v1"
    steps = out.get("steps")
    assert isinstance(steps, list)
    assert any(s.get("action") == "create_payment_and_send_link@v1" for s in steps)
    pay = [s for s in steps if s.get("action") == "create_payment_and_send_link@v1"][0]
    assert int(pay.get("amount")) == 1234


def test_offer_decline_callback_returns_execute_plan_with_message():
    ctx = TelegramCtx(
        state=_DummyState(),
        text="",
        cmd=None,
        args="",
        callback_data="offer:decline:launch",
        callback_query_id="cbq1",
        settings={},
        city="",
        moods=[],
        admin_metrics={},
        is_admin=False,
        roles=[],
        perms=[],
        is_superadmin=False,
        realtime_state={},
        pricing_suggestions={},
        full_access=False,
        pay_status="none",
        selected_tariff={},
        marketing_variants={},
        marketing_seed="1",
        marketing_bandit={},
    )

    out = handle(ctx, default_price_rub=4900)
    assert isinstance(out, dict)
    assert out.get("action") == "execute_plan@v1"
    steps = out.get("steps")
    assert any(s.get("action") == "send_message@v1" for s in steps)
