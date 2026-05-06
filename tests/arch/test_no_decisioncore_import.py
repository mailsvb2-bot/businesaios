from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_decisioncore_import() -> None:
    target = ROOT / "core" / "knowledge" / "__init__.py"
    text = target.read_text(encoding="utf-8", errors="ignore")
    assert "DecisionCore" not in text
