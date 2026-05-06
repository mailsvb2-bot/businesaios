from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_round20_compile_triage_report_exists() -> None:
    path = ROOT / "COMPILE_TRIAGE_REPORT_round20.txt"
    text = path.read_text(encoding="utf-8")
    assert "Round 20: compile triage." in text
    assert "Python files checked:" in text
