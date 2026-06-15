from __future__ import annotations

from scripts.ci.integrity.active_test_index import build_active_test_index


def test_active_test_index_reports_core_architecture_locks() -> None:
    index = build_active_test_index()
    by_id = {item.risk_id: item for item in index.risks}

    assert by_id["P0_NO_SECOND_BRAIN"].test_files_found
    assert by_id["P0_NO_SECOND_BRAIN"].active_gates
    assert by_id["P0_NO_SECOND_BRAIN"].status == "active"

    assert by_id["P0_SINGLE_DECISIONCORE"].test_files_found
    assert by_id["P0_SINGLE_DECISIONCORE"].status in {
        "active",
        "tests_found_but_no_active_gate_detected",
    }


def test_active_test_index_serializes_to_json_shape() -> None:
    payload = build_active_test_index().to_json()

    assert payload["inventory"]["total_test_files"] > 0
    assert payload["inventory"]["all_tests_gate_present"] is True
    assert payload["risks"]
    assert {"risk_id", "test_files_found", "active_gates", "active_steps", "status"} <= set(payload["risks"][0])
