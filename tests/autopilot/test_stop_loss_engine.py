from core.autopilot.stop_loss_engine import StopLossConfig, StopLossState, evaluate_stop_loss


def test_stop_loss_triggers_on_spend_without_conversions():
    cfg = StopLossConfig(max_cac_minor=20000, max_spend_no_conv_minor=3000, min_profit_minor=-2000)
    st = StopLossState(spend_minor=5000, conversions=0, profit_minor=1000, cac_minor=None)
    d = evaluate_stop_loss(cfg, st)
    assert d.triggered
    assert d.reason == "spend_without_conversions"
