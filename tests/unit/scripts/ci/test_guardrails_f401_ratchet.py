from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_guardrails_f401_debt_cannot_regrow() -> None:
    assert ('guardrails', 'F401') in _RATCHETED_STRICT_DEBT
