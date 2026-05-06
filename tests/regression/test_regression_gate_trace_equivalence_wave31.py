from __future__ import annotations

from formal.regression_gate.golden_trace import compare_traces


def test_trace_equivalence_ignores_decision_id_noise() -> None:
    left = {
        "request_id": "req-1",
        "decision_path": "core.ai.decision_core",
        "optimization_target": "route_quality_and_business_value",
        "decision_id": "old",
    }
    right = {
        "request_id": "req-1",
        "decision_path": "core.ai.decision_core",
        "optimization_target": "route_quality_and_business_value",
        "decision_id": "new",
    }
    diff = compare_traces(left, right)
    assert diff.equal is True
    assert diff.differing_keys == ()


def test_trace_equivalence_detects_path_drift() -> None:
    diff = compare_traces(
        {"request_id": "req-1", "decision_path": "core.ai.decision_core"},
        {"request_id": "req-1", "decision_path": "routing"},
    )
    assert diff.equal is False
    assert diff.differing_keys == ("decision_path",)
