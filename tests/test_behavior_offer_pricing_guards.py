from __future__ import annotations

import pytest

from core.behavior.integration.offer_selection_guard import filter_candidates_by_behavior_constraints
from core.behavior.integration.pricing_offer_join import apply_behavior_to_offer_price_candidate
from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1
from core.pricing.rl.guard import PricingSelectionContext
from core.pricing.rl.selection_service import PricingSelectionService


def test_filter_candidates_by_behavior_constraints_removes_disallowed_items() -> None:
    candidates = [
        {"offer_id": "offer_90_a", "aggressive": False, "placement": "normal"},
        {"offer_id": "offer_x", "aggressive": True, "placement": "normal"},
        {"offer_id": "offer_y", "aggressive": False, "placement": "normal"},
    ]
    result = filter_candidates_by_behavior_constraints(candidates, {
        "disallow_offer_prefixes": ("offer_90",), "aggressive_allowed": False, "paywall_first_allowed": True,
    })
    assert [item["offer_id"] for item in result] == ["offer_y"]


def test_apply_behavior_to_offer_price_candidate_caps_band() -> None:
    result = apply_behavior_to_offer_price_candidate(
        {"band": "premium", "pricing_mode": "normal"},
        {"max_band": "low", "mode": "safe", "premium_allowed": False},
    )
    assert result["band"] == "low"
    assert result["pricing_mode"] == "safe"


def test_commercial_candidates_use_canonical_catalog_and_pricing_selector() -> None:
    catalog = YamlOfferCatalogV1.from_spec({"catalog_id": "tenant-a:service:prod", "offers": [
        {"offer_id": "diagnostic", "title": "Диагностика", "base_price_rub": 0,
         "meta": {"commercial": {"position": 0, "min_evidence_score": 0.0}}},
        {"offer_id": "audit", "title": "Аудит", "base_price_rub": 60_000,
         "meta": {"commercial": {"position": 1, "min_evidence_score": 0.55, "requires_human_approval": True}}},
    ]})
    ctx = PricingSelectionContext(tenant_id="tenant-a", decision_id="d1", correlation_id="c1", issuer_id="businesaios-core", action="pricing_select@v1")
    result = PricingSelectionService().select_from_catalog(ctx=ctx, catalog=catalog,
        evidence={"candidate_scores": {"diagnostic": 0.1, "audit": 0.9}}, evidence_score=0.8)
    assert result["selected"]["offer_id"] == "audit" and result["selected"]["price_rub"] == 60_000
    with pytest.raises(ValueError, match="candidate score missing"):
        PricingSelectionService().select_from_catalog(ctx=ctx, catalog=catalog,
            evidence={"candidate_scores": {"diagnostic": 1.0}}, evidence_score=0.8)
