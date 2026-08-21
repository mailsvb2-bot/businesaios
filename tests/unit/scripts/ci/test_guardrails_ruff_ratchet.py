from __future__ import annotations

from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_guardrails_f401_i001_debt_cannot_regrow() -> None:
    assert ('guardrails', 'F401,I001') in _RATCHETED_STRICT_DEBT
