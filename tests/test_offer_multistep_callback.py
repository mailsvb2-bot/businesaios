from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.router import handle


class _DummyState:
    def __init__(self) -> None:
        self.user_id = "u1"
        self.tenant_id = "tenantA"
        self.product = {"product_id": "organization_platform", "domain": "organization_platform"}


def test_offer_accept_callback_routes_to_canonical_commercial_owner_without_untrusted_charge():
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
    assert out.action == "send_message@v1"
    assert out.payload["callback_query_id"] == "cbq1"
    assert out.payload["track_payload"]["payment_confirmed"] is False
    assert out.payload["track_payload"]["offer_id"] == "launch"
    assert "серверный каталог" in out.payload["text"]
    assert "amount" not in out.payload
    assert "steps" not in out.payload
    from core.ux.unified_messenger_menu import BUSINESS_ONBOARDING_URL
    buttons = [b for row in out.payload["reply_markup"]["inline_keyboard"] for b in row]
    assert any(b.get("url") == BUSINESS_ONBOARDING_URL for b in buttons)


def test_offer_decline_callback_uses_single_verified_message_and_receipt():
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
    assert out.action == "send_message@v1"
    assert out.payload["callback_query_id"] == "cbq1"
    assert out.payload["track_payload"]["kind"] == "decline"
    assert "Без давления" in out.payload["text"]
    assert "steps" not in out.payload
