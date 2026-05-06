from __future__ import annotations

from execution.business_memory_governance import BusinessMemoryFitReport
from execution.business_memory_promotion import BusinessMemoryPromotionHelper


def test_business_memory_promotion_helper_builds_evidence() -> None:
    helper = BusinessMemoryPromotionHelper()
    evidence = helper.build_promotion_evidence(
        candidate_record={"run_id": "run-1"},
        business_memory_summary={"total_runs": 4},
        fit_report=BusinessMemoryFitReport(approved=True, score=0.75, reasons=("goal_matches_active_goal",), summary="ok"),
    )
    assert evidence["business_memory_fit"]["approved"] is True
    assert evidence["business_memory_fit"]["score"] == 0.75
    assert evidence["business_memory_summary"]["total_runs"] == 4


def test_business_memory_promotion_helper_scenario_alignment() -> None:
    helper = BusinessMemoryPromotionHelper()
    alignment = helper.scenario_alignment(
        scenario="lead_processing",
        business_memory_summary={
            "active_goals": ["lead processing for inbound demand"],
            "learned_preferences": {"segment": "services"},
        },
    )
    assert alignment.aligned is True
    assert alignment.score > 0.0



def test_business_memory_promotion_helper_canonicalizes_summary_before_alignment() -> None:
    helper = BusinessMemoryPromotionHelper()
    alignment = helper.scenario_alignment(
        scenario="pricing_adjustment",
        business_memory_summary={
            "profile": {"segment": "services"},
            "learned_preferences": {"offer_type": "subscription"},
            "active_goals": ["pricing adjustment", "pricing adjustment"],
            "decision_hint": {"next_action": "raise_prices"},
        },
    )
    assert alignment.aligned is True
    assert alignment.score >= 0.30
    assert "scenario_matches_active_goal" in alignment.reasons
    assert "offer_type_known" in alignment.reasons
