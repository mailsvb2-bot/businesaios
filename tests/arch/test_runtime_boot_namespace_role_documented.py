from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_boot_namespace_role_doc_exists() -> None:
    path = ROOT / "runtime" / "boot" / "CANON_NAMESPACE_ROLE.md"
    text = path.read_text(encoding="utf-8")
    assert "concrete `DecisionCore` construction is allowed only here" in text
