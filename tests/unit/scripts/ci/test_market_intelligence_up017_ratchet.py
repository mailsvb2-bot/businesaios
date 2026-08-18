from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_market_intelligence_up017_debt_cannot_regrow() -> None:
    assert ("market_intelligence", "UP017") in _RATCHETED_STRICT_DEBT
