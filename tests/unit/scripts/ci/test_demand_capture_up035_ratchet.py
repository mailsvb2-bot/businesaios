from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_demand_capture_up035_debt_cannot_regrow() -> None:
    assert ("demand_capture", "UP035") in _RATCHETED_STRICT_DEBT
