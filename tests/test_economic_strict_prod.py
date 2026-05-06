import os


def test_prod_implies_strict(monkeypatch):
    """Production must always run in strict economic mode."""
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("ECONOMIC_STRICT", raising=False)

    from governance.economic_layer import is_strict_mode

    assert is_strict_mode() is True


def test_strict_blocks_missing_states(monkeypatch):
    """In strict mode, missing capital/horizon state must block execution."""
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("ECONOMIC_STRICT", raising=False)

    from governance.economic_layer import EconomicAutonomyLayer

    class DummyDecision:
        cost = 10.0

    class DummyWorld:
        capital = None
        horizon_state = None

    layer = EconomicAutonomyLayer()
    verdict = layer.review(DummyDecision(), DummyWorld())
    assert verdict.allow is False
    assert verdict.reason in {"missing_capital_state", "missing_horizon_state"}
