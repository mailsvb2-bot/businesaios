from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_does_not_define_gate_order() -> None:
    text = (ROOT / "scripts" / "ci" / "bootstrap.py").read_text(encoding="utf-8")
    assert "plan_for_gate" not in text
    assert "doctor-check" not in text
    assert "quality-check" not in text
