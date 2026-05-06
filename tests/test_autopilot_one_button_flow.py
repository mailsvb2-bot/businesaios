from __future__ import annotations

from core.autopilot.loader import load_autopilot_contract_from_env
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.router import handle


class _DummyState:
    def __init__(self) -> None:
        self.user_id = "u1"
        self.tenant_id = "tenantA"
        self.product = {"product_id": "organization_platform", "domain": "organization_platform", "environment": "prod", "autopilot_contract_ref": "default"}


def _base_ctx(*, text: str = "", callback_data: str = "", settings: dict | None = None) -> TelegramCtx:
    return TelegramCtx(
        state=_DummyState(),
        text=text,
        cmd=None,
        args="",
        callback_data=callback_data,
        callback_query_id="cbq1" if callback_data else None,
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
    )


def test_autopilot_contract_loads_default_and_validates():
    c = load_autopilot_contract_from_env(tenant_id="tenantA", ref="default")
    assert c.tenant_id == "tenantA"
    assert c.contract_id
    assert c.north_star_metric in {"profit", "revenue", "retention", "ltv", "cac", "activation_rate"}


def test_autopilot_menu_opens():
    ctx = _base_ctx(callback_data="autopilot:menu")
    out = handle(ctx, default_price_rub=490)
    assert out.action == "send_message@v1"
    assert "Autopilot" in str(out.payload.get("text") or "")


def test_autopilot_start_sets_session():
    ctx = _base_ctx(callback_data="autopilot:start:7d")
    out = handle(ctx, default_price_rub=490)
    assert out.action == "set_user_setting@v1"
    assert out.payload.get("key") == "autopilot:session"
    v = out.payload.get("value")
    assert isinstance(v, dict)
    assert v.get("stage") == "diag:what"
