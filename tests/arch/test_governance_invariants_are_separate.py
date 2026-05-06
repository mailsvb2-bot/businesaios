from pathlib import Path


def test_governance_invariants_are_separate() -> None:
    assert Path("infra/governance_invariants.py").exists()
    assert Path("infra/policy_constitution.py").exists()
