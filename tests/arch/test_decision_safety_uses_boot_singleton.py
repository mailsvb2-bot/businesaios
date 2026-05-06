from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_decision_policy_safety_uses_runtime_boot_singleton() -> None:
    text = (ROOT / "application" / "decision_policy" / "safety.py").read_text(encoding="utf-8")
    assert "from runtime.safety_controls import" in text
    assert "build_default_profile" not in text
    assert "_DEFAULT_PROFILE" not in text
