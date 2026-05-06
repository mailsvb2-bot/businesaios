from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_action_issuance() -> None:
    target = ROOT / "core" / "knowledge" / "service.py"
    text = target.read_text(encoding="utf-8", errors="ignore")
    assert ".issue(" not in text
    assert "final_action" not in text
