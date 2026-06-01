import pytest

from core.strategic_horizon.engine import (
    MAX_RISK_BUDGET,
    MIN_MARGIN_SAFE,
    MIN_RISK_BUDGET,
    MIN_RUNWAY_DEFENSE,
    MIN_RUNWAY_STABILIZE,
    MODE_COOLDOWN_SECONDS,
    EconomyState,
    ExternalContext,
    LearningRegime,
    LearningState,
    ProductState,
    RiskState,
    StrategicHorizonEngine,
    StrategicMode,
    SystemState,
    UserDynamics,
)


def make_state(
    *,
    ts: float = 1_700_000_000.0,
    runway: float = 120.0,
    margin: float = 0.3,
    churn: float = 0.05,
    growth: float = 0.08,
    offline_score: float = 0.75,
    online_conf: float = 0.65,
    divergence: float = 0.1,
    fin_risk: float = 0.2,
    ux_risk: float = 0.2,
    reg_risk: float = 0.2,
) -> SystemState:
    return SystemState(
        ts=ts,
        economy=EconomyState(
            ltv_mean=10000.0,
            cac_mean=2000.0,
            margin=margin,
            cash_runway_days=runway,
        ),
        users=UserDynamics(
            retention_d1=0.6,
            retention_d7=0.35,
            retention_d30=0.2,
        ),
        learning=LearningState(
            offline_score=offline_score,
            online_reward_confidence=online_conf,
            policy_divergence=divergence,
        ),
        risk=RiskState(
            financial_risk=fin_risk,
            ux_risk=ux_risk,
            regulatory_risk=reg_risk,
        ),
        product=ProductState(
            growth_rate=growth,
            churn_rate=churn,
        ),
        external=ExternalContext(
            seasonality=1.0,
            market_pressure=0.5,
        ),
    )


def test_determinism_same_input_same_output():
    eng = StrategicHorizonEngine()
    s = make_state()

    v1 = eng.evaluate(s)
    v2 = eng.evaluate(s)

    assert v1 == v2


def test_output_types_and_fields_present():
    eng = StrategicHorizonEngine()
    s = make_state()
    v = eng.evaluate(s)

    assert isinstance(v.mode, StrategicMode)
    assert isinstance(v.learning_regime, LearningRegime)
    assert isinstance(v.horizon_days, int)
    assert 0.0 <= v.risk_budget <= 1.0
    assert 0.0 <= v.growth_pressure <= 1.0
    assert v.evaluated_at == s.ts


def test_defense_if_runway_below_min_defense():
    eng = StrategicHorizonEngine()
    s = make_state(runway=MIN_RUNWAY_DEFENSE - 0.01)

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.DEFENSE


def test_defense_if_financial_risk_high():
    eng = StrategicHorizonEngine()
    s = make_state(fin_risk=0.81)

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.DEFENSE


def test_defense_if_policy_divergence_high():
    eng = StrategicHorizonEngine()
    s = make_state(divergence=0.71)

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.DEFENSE


def test_stabilize_if_runway_below_min_stabilize_but_not_defense():
    eng = StrategicHorizonEngine()
    s = make_state(runway=MIN_RUNWAY_STABILIZE - 0.01, fin_risk=0.2, divergence=0.1)
    assert s.economy.cash_runway_days >= MIN_RUNWAY_DEFENSE

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.STABILIZE


def test_stabilize_if_margin_below_min_margin_safe():
    eng = StrategicHorizonEngine()
    s = make_state(margin=MIN_MARGIN_SAFE - 0.001, runway=120.0)

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.STABILIZE


def test_expand_when_expand_conditions_met():
    eng = StrategicHorizonEngine()
    s = make_state(
        margin=0.30,
        growth=0.06,
        churn=0.04,
        offline_score=0.80,
        fin_risk=0.3,
    )

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.EXPAND


def test_optimize_when_optimize_conditions_met_but_expand_not_met():
    eng = StrategicHorizonEngine()
    s = make_state(
        margin=0.20,
        growth=0.01,
        offline_score=0.60,
        online_conf=0.55,
        fin_risk=0.4,
    )

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.OPTIMIZE


def test_research_fallback_when_no_other_mode_matches():
    eng = StrategicHorizonEngine()
    s = make_state(
        margin=0.17,
        growth=0.01,
        offline_score=0.6,
        online_conf=0.4,
        fin_risk=0.2,
        runway=120.0,
        churn=0.05,
    )

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.RESEARCH


@pytest.mark.parametrize(
    "mode,expected",
    [
        (StrategicMode.DEFENSE, 7),
        (StrategicMode.STABILIZE, 14),
        (StrategicMode.OPTIMIZE, 30),
        (StrategicMode.EXPAND, 45),
        (StrategicMode.RESEARCH, 21),
    ],
)
def test_horizon_mapping(mode, expected):
    eng = StrategicHorizonEngine()
    if mode == StrategicMode.DEFENSE:
        s = make_state(runway=MIN_RUNWAY_DEFENSE - 0.01)
    elif mode == StrategicMode.STABILIZE:
        s = make_state(runway=MIN_RUNWAY_STABILIZE - 0.01)
    elif mode == StrategicMode.EXPAND:
        s = make_state(margin=0.30, growth=0.06, offline_score=0.80, fin_risk=0.2)
    elif mode == StrategicMode.OPTIMIZE:
        s = make_state(margin=0.20, online_conf=0.55, growth=0.01, offline_score=0.60, fin_risk=0.3)
    else:
        s = make_state(margin=0.17, online_conf=0.4, growth=0.01, offline_score=0.60)

    v = eng.evaluate(s)
    assert v.mode == mode
    assert v.horizon_days == expected


def test_risk_budget_clamped_min_max():
    eng = StrategicHorizonEngine()

    s_low_risk = make_state(fin_risk=0.0, ux_risk=0.0, reg_risk=0.0)
    v1 = eng.evaluate(s_low_risk)
    assert MIN_RISK_BUDGET <= v1.risk_budget <= MAX_RISK_BUDGET

    eng2 = StrategicHorizonEngine()
    s_high_risk = make_state(fin_risk=1.0, ux_risk=1.0, reg_risk=1.0, runway=120.0, divergence=0.1)
    v2 = eng2.evaluate(s_high_risk)
    assert v2.risk_budget == pytest.approx(MIN_RISK_BUDGET)


def test_risk_budget_defense_is_lower_than_optimize_given_same_risks():
    s_defense = make_state(runway=MIN_RUNWAY_DEFENSE - 0.01, fin_risk=0.2, ux_risk=0.2, reg_risk=0.2)
    s_opt = make_state(runway=120.0, margin=0.20, online_conf=0.6, growth=0.01, offline_score=0.6,
                       fin_risk=0.2, ux_risk=0.2, reg_risk=0.2)

    e1 = StrategicHorizonEngine()
    v_def = e1.evaluate(s_defense)

    e2 = StrategicHorizonEngine()
    v_opt = e2.evaluate(s_opt)

    assert v_def.mode == StrategicMode.DEFENSE
    assert v_opt.mode == StrategicMode.OPTIMIZE
    assert v_def.risk_budget < v_opt.risk_budget


def test_learning_frozen_in_defense():
    eng = StrategicHorizonEngine()
    s = make_state(runway=MIN_RUNWAY_DEFENSE - 0.01, offline_score=0.9, online_conf=0.9)

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.DEFENSE
    assert v.learning_regime == LearningRegime.FROZEN


def test_learning_frozen_if_offline_score_low_even_if_not_defense():
    eng = StrategicHorizonEngine()
    s = make_state(offline_score=0.49, runway=120.0, margin=0.3)

    v = eng.evaluate(s)
    assert v.learning_regime == LearningRegime.FROZEN


def test_learning_aggressive_only_in_expand_with_high_online_confidence():
    eng = StrategicHorizonEngine()
    s = make_state(
        margin=0.30,
        growth=0.06,
        offline_score=0.80,
        online_conf=0.71,
        fin_risk=0.2,
    )

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.EXPAND
    assert v.learning_regime == LearningRegime.AGGRESSIVE


def test_learning_safe_in_optimize():
    eng = StrategicHorizonEngine()
    s = make_state(margin=0.20, online_conf=0.6, growth=0.01, offline_score=0.6, fin_risk=0.3)

    v = eng.evaluate(s)
    assert v.mode == StrategicMode.OPTIMIZE
    assert v.learning_regime == LearningRegime.SAFE


def test_growth_pressure_low_in_defense_and_stabilize():
    eng = StrategicHorizonEngine()

    v_def = eng.evaluate(make_state(runway=MIN_RUNWAY_DEFENSE - 0.01))
    assert v_def.mode == StrategicMode.DEFENSE
    assert v_def.growth_pressure == pytest.approx(0.1)

    eng2 = StrategicHorizonEngine()
    v_stab = eng2.evaluate(make_state(runway=MIN_RUNWAY_STABILIZE - 0.01))
    assert v_stab.mode == StrategicMode.STABILIZE
    assert v_stab.growth_pressure == pytest.approx(0.1)


def test_growth_pressure_in_expand_is_higher_than_optimize_for_same_signals():
    s_expand = make_state(margin=0.30, growth=0.06, offline_score=0.80, fin_risk=0.2, churn=0.05)
    s_opt = make_state(margin=0.20, online_conf=0.6, growth=0.01, offline_score=0.6, fin_risk=0.3, churn=0.05)

    e1 = StrategicHorizonEngine()
    v_expand = e1.evaluate(s_expand)

    e2 = StrategicHorizonEngine()
    v_opt = e2.evaluate(s_opt)

    assert v_expand.mode == StrategicMode.EXPAND
    assert v_opt.mode == StrategicMode.OPTIMIZE
    assert v_expand.growth_pressure >= v_opt.growth_pressure


def test_mode_cooldown_prevents_fast_switch():
    eng = StrategicHorizonEngine()
    t0 = 1_700_000_000.0

    s1 = make_state(
        ts=t0,
        margin=0.30,
        growth=0.06,
        offline_score=0.80,
        fin_risk=0.2,
    )
    v1 = eng.evaluate(s1)
    assert v1.mode == StrategicMode.EXPAND

    s2 = make_state(
        ts=t0 + (MODE_COOLDOWN_SECONDS - 1),
        runway=MIN_RUNWAY_DEFENSE - 0.01,
        fin_risk=0.9,
    )
    v2 = eng.evaluate(s2)
    assert v2.mode == StrategicMode.EXPAND


def test_mode_switch_after_cooldown_allows_transition():
    eng = StrategicHorizonEngine()
    t0 = 1_700_000_000.0

    s1 = make_state(
        ts=t0,
        margin=0.30,
        growth=0.06,
        offline_score=0.80,
        fin_risk=0.2,
    )
    v1 = eng.evaluate(s1)
    assert v1.mode == StrategicMode.EXPAND

    s2 = make_state(
        ts=t0 + MODE_COOLDOWN_SECONDS + 1,
        runway=MIN_RUNWAY_DEFENSE - 0.01,
        fin_risk=0.9,
    )
    v2 = eng.evaluate(s2)
    assert v2.mode == StrategicMode.DEFENSE
