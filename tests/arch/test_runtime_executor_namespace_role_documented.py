from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_runtime_executor_namespace_role_doc_exists() -> None:
    p = ROOT / "runtime" / "executor" / "CANON_NAMESPACE_ROLE.md"
    text = p.read_text(encoding="utf-8")
    assert "Must NOT contain" in text
    assert "decision generation" in text
