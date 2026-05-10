from application.decision_runtime.canonical_flow_contract import (
    CANONICAL_FLOW_STAGES,
    is_canonical_flow_complete,
)

def test_canonical_flow_contract_has_expected_stage_order() -> None:
    assert CANONICAL_FLOW_STAGES == (
        "signal",
        "state",
        "decision",
        "policy_guard",
        "execution",
        "verification",
        "evidence",
        "memory_archive",
    )

def test_canonical_flow_completeness_check() -> None:
    assert is_canonical_flow_complete(CANONICAL_FLOW_STAGES)
    assert not is_canonical_flow_complete(("signal", "state", "decision"))
