import pytest

from governance.economic_layer import EconomicAutonomyLayer


class DummyDecision:
    cost = 10.0


class DummyWorld:
    capital = None
    horizon_state = None


def test_strict_mode_blocks_without_states(monkeypatch):
    monkeypatch.setenv("ECONOMIC_STRICT", "1")
    layer = EconomicAutonomyLayer()
    verdict = layer.review(DummyDecision(), DummyWorld())
    assert verdict.allow is False
