from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_offer_advisory_contract_exists() -> None:
    path = ROOT / "core" / "offers" / "offer_advisory_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class OfferAdvisoryPort" in text
    assert "OFFER_ADVISORY_CONTRACT_VERSION" in text


def test_economics_advisory_contract_exists() -> None:
    path = ROOT / "core" / "economics" / "economics_advisory_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class EconomicsAdvisoryPort" in text
    assert "ECONOMICS_ADVISORY_CONTRACT_VERSION" in text
