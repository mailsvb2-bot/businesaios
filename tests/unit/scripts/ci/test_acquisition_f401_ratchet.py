from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_acquisition_strict_debt_cannot_regrow() -> None:
    assert ("acquisition", "E402,F401,I001,SIM101,UP035,UP038") in _RATCHETED_STRICT_DEBT
