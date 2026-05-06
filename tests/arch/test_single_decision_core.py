from __future__ import annotations

from pathlib import Path


def test_single_decision_core_exists() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "core" / "ai" / "decision_core.py"
    assert target.exists(), "DecisionCore must exist"
