from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_offers_engine_surface_stays_advisory() -> None:
    path = ROOT / "core" / "offers" / "engine.py"
    text = path.read_text(encoding="utf-8")
    assert "Contract:" in text
    assert "Side-effects: none" in text
    assert ".issue(" not in text


def test_economics_capital_allocation_surface_stays_advisory() -> None:
    path = ROOT / "core" / "economics" / "capital_allocation_engine.py"
    text = path.read_text(encoding="utf-8")
    assert "CapitalAllocationEngine" in text
    assert ".issue(" not in text


def test_economics_has_advisory_boundary_guard() -> None:
    path = ROOT / "core" / "economics" / "guards" / "advisory_boundary_guard.py"
    text = path.read_text(encoding="utf-8")
    assert "advisory" in text.lower()
