from pathlib import Path


def test_policy_snapshots_are_separate() -> None:
    assert Path("infra/policy_snapshots.py").exists()
    assert Path("infra/incident_mode.py").exists()
