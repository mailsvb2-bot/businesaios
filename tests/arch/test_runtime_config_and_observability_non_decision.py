from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_runtime_config_contains_no_decision_calls():
    path = ROOT / "runtime" / "config"
    if path.exists():
        for f in path.rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            assert ".issue(" not in text

def test_runtime_observability_contains_no_decision_calls():
    path = ROOT / "runtime" / "observability"
    if path.exists():
        for f in path.rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            assert ".issue(" not in text
