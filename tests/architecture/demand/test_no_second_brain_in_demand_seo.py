from __future__ import annotations

from pathlib import Path


DEMAND_SEO_ADAPTERS = (
    "location_page_generator.py",
    "service_page_generator.py",
    "rank_tracking.py",
    "local_intent_page_builder.py",
)


def test_demand_seo_adapters_stay_thin() -> None:
    root = Path("demand_seo")
    for name in DEMAND_SEO_ADAPTERS:
        text = (root / name).read_text(encoding="utf-8")
        assert "growth.seo" in text
        assert "CampaignEngine" not in text


def test_demand_seo_does_not_redeclare_growth_location_contracts() -> None:
    root = Path("demand_seo")
    forbidden = {
        "build_location_page_spec",
        "build_service_page_spec",
        "observe_rank_tracking",
        "map_local_intent",
    }
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path} must stay adapter-only, found {marker}"
