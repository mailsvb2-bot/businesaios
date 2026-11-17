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
        roles=["owner"],
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


def test_ads_apply_toggle_uses_single_canonical_settings_operation() -> None:
    from core.ads.apply_gate import AdsApplyState, build_ads_apply_toggle_action

    for callback, expected in (
        ("ads:apply:enable", True), ("ads:apply:disable", False),
    ):
        out = handle(_ctx(callback_data=callback), default_price_rub=490)
        assert out.action == "set_user_setting@v1"
        assert out.payload["key"] == "ads:apply_enabled"
        assert out.payload["value"]["enabled"] is expected
        assert out.payload["callback_query_id"] == "cbq1"
        assert AdsApplyState.from_settings({
            out.payload["key"]: out.payload["value"],
        }).enabled is expected
        assert out.payload["value"]["since_ms"] >= 0
        assert "execute_plan" not in str(out.payload)
    assert AdsApplyState.from_settings({"ads:apply_enabled": True}).enabled
    assert not AdsApplyState.from_settings({"ads:apply_enabled": False}).enabled
    assert not AdsApplyState.from_settings({"ads:apply_enabled": {"enabled": "false", "since_ms": 3}}).enabled
    assert not AdsApplyState.from_settings({"ads:apply_enabled": {"enabled": False, "since_ms": 3}}).since_ms
    assert build_ads_apply_toggle_action(user_id="1", enabled=True, now_ms=123)["value"]["since_ms"] == 123



def test_ads_apply_menu_renders_message() -> None:
    out = handle(_ctx(callback_data="ads:apply:menu", settings={"ads:apply_enabled": True}), default_price_rub=490)
    assert out.action == "send_message@v1"
    assert "Ads Apply" in str(out.payload.get("text") or "")
