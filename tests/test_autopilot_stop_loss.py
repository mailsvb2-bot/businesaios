from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.router import handle


class _DummyState:
    def __init__(self) -> None:
        self.user_id = "u1"
        self.tenant_id = "tenantA"
        self.product = {
            "product_id": "organization_platform",
            "domain": "organization_platform",
            "environment": "prod",
            "autopilot_contract_ref": "stop_loss_test",
        }


def _ctx(*, callback_data: str, settings: dict | None = None, dashboard: dict | None = None) -> TelegramCtx:
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
        autopilot_dashboard=dict(dashboard or {}),
    )


def test_autopilot_launch_triggers_stop_loss_plan():
    settings = {
        "autopilot:session": {"stage": "ready:launch", "diag": {"avg_check_rub": 500, "margin_pct": 50, "leads_per_day": 3}},
    }
    dashboard = {"today": {"profit_minor": -200, "cac_minor": 0, "leads": 0, "purchases": 0, "revenue_minor": 0}}
    out = handle(_ctx(callback_data="autopilot:launch", settings=settings, dashboard=dashboard), default_price_rub=490)
    assert out.action == "execute_plan@v1"
    steps = list(out.payload.get("steps") or [])
    assert any(s.get("action") == "set_user_setting@v1" and s.get("payload", {}).get("key") == "autopilot:stop_loss" for s in steps)


def test_autopilot_can_clear_stop_loss():
    settings = {"autopilot:stop_loss": {"active": True, "reason": "STOP_LOSS_PROFIT", "since_ms": 1}}
    out = handle(_ctx(callback_data="autopilot:stop_loss:clear", settings=settings), default_price_rub=490)
    assert out.action == "execute_plan@v1"
    steps = list(out.payload.get("steps") or [])
    assert any(s.get("action") == "set_user_setting@v1" and s.get("payload", {}).get("key") == "autopilot:stop_loss" for s in steps)
