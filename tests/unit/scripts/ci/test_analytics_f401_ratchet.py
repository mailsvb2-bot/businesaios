from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_analytics_f401_debt_cannot_regrow() -> None:
    assert ("analytics", "F401") in _RATCHETED_STRICT_DEBT
