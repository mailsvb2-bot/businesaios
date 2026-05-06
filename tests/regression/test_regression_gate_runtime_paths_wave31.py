from __future__ import annotations

from formal.regression_gate.path_matrix import RuntimePathCase, run_runtime_path_case


class _Action:
    pass


def test_runtime_decision_core_blocks_without_executor_side_effects() -> None:
    outcome = run_runtime_path_case(
        RuntimePathCase(
            name="blocked",
            governance_allowed=False,
            action=_Action(),
            expected_status="blocked",
            expected_executor_calls=0,
        )
    )
    assert outcome["result"]["status"] == "blocked"
    assert outcome["governance_calls"] == 1
    assert outcome["executor_calls"] == 0
    assert outcome["result"]["reason"] == "governance_rejected"


def test_runtime_decision_core_executes_only_after_governance_allow() -> None:
    outcome = run_runtime_path_case(
        RuntimePathCase(
            name="allowed",
            governance_allowed=True,
            action=_Action(),
            expected_status="executed",
            expected_executor_calls=1,
        )
    )
    assert outcome["result"]["status"] == "executed"
    assert outcome["governance_calls"] == 1
    assert outcome["executor_calls"] == 1
