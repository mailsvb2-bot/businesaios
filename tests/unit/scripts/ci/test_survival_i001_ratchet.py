from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_survival_i001_debt_cannot_regrow() -> None:
    assert ("survival", "I001") in _RATCHETED_STRICT_DEBT
