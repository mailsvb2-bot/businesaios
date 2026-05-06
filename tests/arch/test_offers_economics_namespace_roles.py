from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_offers_namespace_role_doc_exists() -> None:
    path = ROOT / "core" / "offers" / "CANON_NAMESPACE_ROLE.md"
    text = path.read_text(encoding="utf-8")
    assert "Must NOT contain" in text
    assert "final decision issuance" in text


def test_economics_namespace_role_doc_exists() -> None:
    path = ROOT / "core" / "economics" / "CANON_NAMESPACE_ROLE.md"
    text = path.read_text(encoding="utf-8")
    assert "Must NOT contain" in text
    assert "hidden decision authority" in text
