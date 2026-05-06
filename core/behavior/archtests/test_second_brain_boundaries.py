from __future__ import annotations

def assert_behavior_module_boundaries(module_exports: set[str]) -> None:
    forbidden = {
        "execute_action",
        "select_offer",
        "pick_winner",
        "commit_price",
    }
    overlap = module_exports.intersection(forbidden)
    if overlap:
        raise AssertionError(f"Second-brain boundary violation: {sorted(overlap)}")


def test_behavior_module_boundaries_accepts_readonly_exports() -> None:
    assert_behavior_module_boundaries({"build_behavioral_state", "build_person_behavior_snapshot"})
