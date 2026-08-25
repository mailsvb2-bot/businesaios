from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_marketplace_e402_i001_up035_debt_cannot_regrow() -> None:
    assert ("marketplace", "E402,I001,UP035") in _RATCHETED_STRICT_DEBT
