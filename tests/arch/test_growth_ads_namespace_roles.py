from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_growth_ads_namespace_role_doc_exists() -> None:
    path = ROOT / "core" / "growth" / "ads" / "CANON_NAMESPACE_ROLE.md"
    text = path.read_text(encoding="utf-8")
    assert "Must NOT contain" in text
    assert "direct irreversible apply execution" in text

def test_runtime_ads_autopilot_namespace_role_doc_exists() -> None:
    path = ROOT / "runtime" / "handlers" / "ads_autopilot" / "CANON_NAMESPACE_ROLE.md"
    text = path.read_text(encoding="utf-8")
    assert "Must NOT contain" in text
    assert "alternative execution paths" in text
