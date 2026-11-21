"""P2-47: launch preview never authorizes effects."""
from headless.acquisition_execution import promotion_launch_preview
from interfaces.ads.registry import CONNECTORS


def test_launch_preview_never_authorizes_spend():
    preview = promotion_launch_preview(
        plan={"feasible": True, "recommended_daily_budget": 1000.0}, sustainable=True,
        provider="yandex_direct", connectors=CONNECTORS,
    )
    assert preview["weekly_cap_minor"] == 700_000
    assert preview["spend_authorized"] is False and preview["provider_contacted"] is False
    assert preview["requires_human_approval"] is True
    assert "provider_production_ready" in preview["blockers"]


def test_invalid_daily_budget_never_creates_authorization():
    for budget in (float("nan"), float("inf"), -1, None, False):
        out = promotion_launch_preview(plan={"feasible": True, "recommended_daily_budget": budget},
                                       sustainable=True, provider="missing", connectors={})
        assert out["weekly_cap_minor"] == 0 and out["apply_possible"] is False
