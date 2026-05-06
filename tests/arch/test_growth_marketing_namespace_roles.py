from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_growth_namespace_role_doc_exists() -> None:
    path = ROOT / "core" / "growth" / "CANON_NAMESPACE_ROLE.md"
    text = path.read_text(encoding="utf-8")
    assert "Must NOT contain" in text
    assert "final decision issuance" in text


def test_marketing_namespace_role_doc_exists() -> None:
    path = ROOT / "core" / "marketing" / "CANON_NAMESPACE_ROLE.md"
    text = path.read_text(encoding="utf-8")
    assert "Must NOT contain" in text
    assert "decision issuance" in text
