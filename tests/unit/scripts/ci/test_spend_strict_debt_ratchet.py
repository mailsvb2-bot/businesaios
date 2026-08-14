from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_spend_strict_debt_cannot_regrow() -> None:
    assert ("spend", "I001,UP034,UP035") in _RATCHETED_STRICT_DEBT
