from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_matching_up035_debt_cannot_regrow() -> None:
    assert ("matching", "UP035") in _RATCHETED_STRICT_DEBT
