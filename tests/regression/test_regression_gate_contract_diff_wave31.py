from __future__ import annotations

from formal.regression_gate.differential import compare_contracts


def test_contract_diff_ignores_only_decision_id_noise() -> None:
    left = {
        "request_id": "req-1",
        "selected_business_id": "biz-1",
        "requires_manual_review": False,
        "trace": {
            "request_id": "req-1",
            "decision_path": "core.ai.decision_core",
            "optimization_target": "route_quality_and_business_value",
            "decision_id": "old",
        },
    }
    right = {
        "request_id": "req-1",
        "selected_business_id": "biz-1",
        "requires_manual_review": False,
        "trace": {
            "request_id": "req-1",
            "decision_path": "core.ai.decision_core",
            "optimization_target": "route_quality_and_business_value",
            "decision_id": "new",
        },
    }
    diff = compare_contracts(left, right)
    assert diff.equal is False  # top-level trace still differs as a whole object unless explicitly compared by trace helper
    assert diff.differing_keys == ("trace",)


def test_contract_diff_detects_real_regression() -> None:
    diff = compare_contracts(
        {"status": "executed", "trace": {"decision_path": "core.ai.decision_core"}},
        {"status": "blocked", "trace": {"decision_path": "core.ai.decision_core"}},
    )
    assert diff.equal is False
    assert "status" in diff.differing_keys
