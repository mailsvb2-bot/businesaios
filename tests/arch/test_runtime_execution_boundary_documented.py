from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_runtime_execution_boundary_doc_exists() -> None:
    p = ROOT / "runtime" / "CANON_EXECUTION_BOUNDARY.md"
    text = p.read_text(encoding="utf-8")
    assert "ONLY place where irreversible side-effects may occur" in text
    assert "Must NOT:" in text
