from pathlib import Path


def test_retention_adapter_exposes_evidence_candidates_without_hidden_selection_v26():
    text = Path("core/retention/decision_adapter.py").read_text(encoding="utf-8")
    assert "propose_candidates" in text
    assert "compute_evidence" in text
    assert "selected_candidate_id" not in text.split("def propose_candidates", 1)[1].split("def maybe_decide_offer", 1)[0]
    assert "build_retention_debug" not in text


def test_unified_policy_delegates_candidate_ranking_to_decision_core_v26():
    text = Path("core/policies/telegram/unified_policy.py").read_text(encoding="utf-8")
    assert "apply_retention_constraints_to_state" in text
    assert "propose_candidates" in text
    assert "merge_retention_plan" not in text
