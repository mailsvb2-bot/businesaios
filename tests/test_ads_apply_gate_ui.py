from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.router import handle


class _DummyState:
    def __init__(self) -> None:
        self.user_id = "u1"
        self.tenant_id = "t1"
        self.product = {"product_id": "businesaios", "domain": "businesaios", "environment": "prod"}


def _ctx(*, callback_data: str, settings: dict | None = None) -> TelegramCtx:
    return TelegramCtx(
        state=_DummyState(),
        text="",
        cmd=None,
        args="",
        callback_data=callback_data,
        callback_query_id="cbq1",
        settings=dict(settings or {}),
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
        autopilot_dashboard={},
    )


def test_ads_apply_enable_builds_execute_plan() -> None:
    out = handle(_ctx(callback_data="ads:apply:enable"), default_price_rub=490)
    assert out.action == "execute_plan@v1"
    steps = list(out.payload.get("steps") or [])
    assert any(s.get("action") == "set_user_setting@v1" and s.get("payload", {}).get("key") == "ads:apply_enabled" for s in steps)


def test_ads_apply_menu_renders_message() -> None:
    out = handle(_ctx(callback_data="ads:apply:menu", settings={"ads:apply_enabled": True}), default_price_rub=490)
    assert out.action == "send_message@v1"
    assert "Ads Apply" in str(out.payload.get("text") or "")
