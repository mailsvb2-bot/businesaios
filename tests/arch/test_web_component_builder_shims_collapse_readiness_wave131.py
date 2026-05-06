from __future__ import annotations

from app.web.components import COMPONENT_BUILDERS


def test_component_builders_live_on_package_root() -> None:
    assert COMPONENT_BUILDERS["AutopilotButton"].KIND == "autopilot_button"
    assert COMPONENT_BUILDERS["RevenueCard"].KIND == "revenue_card"


def test_package_root_exposes_builder_symbols() -> None:
    import app.web.components as components

    assert components.AutopilotButton.KIND == "autopilot_button"
    assert components.CampaignStatusCard.KIND == "campaign_status_card"
    assert components.RevenueCard.KIND == "revenue_card"
