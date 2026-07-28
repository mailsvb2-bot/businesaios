from pathlib import Path


def test_retention_engine_split_into_single_purpose_helpers():
    engine = Path("core/retention/engine.py").read_text(encoding="utf-8")
    candidates = Path("core/retention/engine_candidates.py").read_text(encoding="utf-8")
    materialization = Path("core/retention/engine_materialization.py").read_text(encoding="utf-8")
    models = Path("core/retention/engine_models.py").read_text(encoding="utf-8")

    assert "score_arm_candidates_event_sourced" in engine
    assert "_build_offer_candidates" in engine
    assert "base_price_fn=base_price_for_arm" in engine
    assert "price_candidates_fn=build_price_candidates" in engine
    assert "RetentionOfferCandidate" in models
    assert "price_candidates_fn" in candidates
    assert "selected_by_decision_core" in materialization
    assert "choose_arm" not in engine
    assert "merge_retention_plan" not in engine
    assert len(engine.splitlines()) < 260
