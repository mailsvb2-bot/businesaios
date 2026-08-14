from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_intent_strict_debt_cannot_regrow() -> None:
    assert ("intent", "I001") in _RATCHETED_STRICT_DEBT
