from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_contracts_i001_debt_cannot_regrow() -> None:
    assert ("contracts", "I001") in _RATCHETED_STRICT_DEBT
