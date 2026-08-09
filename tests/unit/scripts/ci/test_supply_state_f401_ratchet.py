from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_supply_state_f401_debt_cannot_regrow() -> None:
    assert ("supply_state", "F401") in _RATCHETED_STRICT_DEBT
