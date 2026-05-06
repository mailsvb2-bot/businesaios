from __future__ import annotations
from execution.business_memory_matcher import BusinessMemoryMatcher
from execution.business_memory_taxonomy import BusinessMemoryTaxonomy
from execution.business_operating_memory import FileBusinessOperatingMemoryStore

def test_business_memory_taxonomy_normalizes_failure_and_outcomes() -> None:
    taxonomy = BusinessMemoryTaxonomy()
    payload = taxonomy.normalize_feedback(completed=False, stop_reason="manual_review_required", final_feedback={"error": "rate limit", "normalized_outcome": {"channel": "Search"}})
    assert payload.failure_kind == "rate_limit"
    assert payload.outcome_kinds == ("channel=search",)
    assert "failure:rate_limit" in payload.evidence_labels

def test_business_memory_matcher_returns_similar_runs(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    store.remember_execution(tenant_id="t1", business_id="b1", run_id="run-1", goal="acquire new clients", completed=True, stop_reason="goal_reached", final_feedback={"goal_score": 0.9, "goal_reached": True}, step_count=1, profile={"segment": "services", "offer_type": "consulting", "traffic_source": "search"}, constraints={}, signals=[], meta={}, channel="google_ads", region="eu", product_name="BusinesAIOS")
    matcher = BusinessMemoryMatcher()
    target = matcher.build_fingerprint(goal="acquire qualified leads", profile={"segment": "services", "offer_type": "consulting", "traffic_source": "search"}, meta={}, channel="google_ads", region="eu")
    matches = matcher.select_similar_runs(memory=store.load(tenant_id="t1", business_id="b1"), target=target)
    assert matches and matches[0].run_id == "run-1" and matches[0].score > 0.5
