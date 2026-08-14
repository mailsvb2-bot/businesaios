from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_quality_i001_and_up035_debt_cannot_regrow() -> None:
    assert ("quality", "I001,UP035") in _RATCHETED_STRICT_DEBT
