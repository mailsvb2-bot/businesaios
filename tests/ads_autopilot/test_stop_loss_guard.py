from core.ads.autopilot.stop_loss_guard import StopLossGuard


def test_stop_loss_blocks_on_spend():
    g = StopLossGuard(max_spend_minor=100, max_cpa_minor=0, min_roas_x1000=0)
    d = g.evaluate({"spend_minor": 150})
    assert d.allowed is False
    assert d.reason == "max_spend_reached"


def test_stop_loss_allows_ok():
    g = StopLossGuard(max_spend_minor=100, max_cpa_minor=50, min_roas_x1000=0)
    d = g.evaluate({"spend_minor": 10, "conversions": 1})
    assert d.allowed is True
