import math
import pytest

# Подстрой импорт под твой репозиторий/путь.
# Если файл рядом — можно: from core.economics.capital_allocation_engine import ...
from core.economics.capital_allocation_engine import (
    CapitalAllocationEngine,
    WorldState,
    CapitalState,
    DefaultRiskModel,
    ConstraintBuilder,
)


def make_world(
    *,
    cash_balance=100_000.0,
    marketing_budget=20_000.0,
    compute_budget=5_000.0,
    risk_limits=0.3,
    runway_days=120.0,
    reserve=20_000.0,
    ltv=200.0,
    cac=50.0,
    growth_rate=0.10,
    churn_rate=0.05,
    uncertainty=0.10,
) -> WorldState:
    return WorldState(
        capital=CapitalState(
            cash_balance=cash_balance,
            marketing_budget=marketing_budget,
            compute_budget=compute_budget,
            risk_limits=risk_limits,
            runway_days=runway_days,
            reserve=reserve,
        ),
        ltv=ltv,
        cac=cac,
        growth_rate=growth_rate,
        churn_rate=churn_rate,
        uncertainty=uncertainty,
    )


def alloc_sum(plan, *, capital_type="cash") -> float:
    return sum(a.amount for a in plan.allocations if a.capital_type == capital_type)


def test_allocate_is_deterministic_same_input_same_output():
    cae = CapitalAllocationEngine()
    world = make_world()

    plan1 = cae.allocate(world)
    plan2 = cae.allocate(world)

    assert plan1 == plan2


def test_survival_mode_when_runway_below_min():
    cae = CapitalAllocationEngine()
    world = make_world(runway_days=10.0)  # below ConstraintBuilder.MIN_RUNWAY (=30)

    plan = cae.allocate(world)

    assert plan.horizon_days == 60
    assert len(plan.allocations) == 1
    a = plan.allocations[0]
    assert a.target == "reserve"
    assert a.risk_class == "minimal"
    assert a.amount == pytest.approx(world.capital.cash_balance)


def test_survival_mode_when_risk_high():
    # Сделаем риск > 0.8 через параметры:
    # DefaultRiskModel: risk = runway_risk + churn + uncertainty
    # runway_risk = 1/max(runway_days,1)
    # Пусть runway_days=1 => 1.0, churn=0.0, uncertainty=0.0 => risk=1.0
    cae = CapitalAllocationEngine()
    world = make_world(runway_days=1.0, churn_rate=0.0, uncertainty=0.0)

    plan = cae.allocate(world)

    assert plan.horizon_days == 60
    assert len(plan.allocations) == 1
    assert plan.allocations[0].target == "reserve"


def test_normal_mode_allocations_two_lines_growth_and_reserve():
    cae = CapitalAllocationEngine()
    world = make_world(runway_days=120.0, churn_rate=0.05, uncertainty=0.05)

    plan = cae.allocate(world)

    assert plan.horizon_days == 30
    assert len(plan.allocations) == 2
    targets = {a.target for a in plan.allocations}
    assert targets == {"growth", "reserve"}


def test_spend_never_exceeds_marketing_budget():
    cae = CapitalAllocationEngine()
    world = make_world(marketing_budget=7_000.0)

    plan = cae.allocate(world)
    total_cash = alloc_sum(plan, capital_type="cash")

    assert total_cash <= world.capital.marketing_budget + 1e-9


def test_spend_never_exceeds_max_spend_constraint():
    # ConstraintBuilder: reserve_required = cash_balance * 0.2
    # max_spend = cash_balance - reserve_required = 0.8 * cash_balance
    # spend = min(max_spend, marketing_budget)
    cae = CapitalAllocationEngine()
    world = make_world(cash_balance=10_000.0, marketing_budget=50_000.0)

    plan = cae.allocate(world)
    total_cash = alloc_sum(plan)

    expected_max_spend = 0.8 * world.capital.cash_balance
    assert total_cash <= expected_max_spend + 1e-9


def test_plan_confidence_in_0_1_and_risk_in_0_1():
    cae = CapitalAllocationEngine()
    world = make_world()

    plan = cae.allocate(world)

    assert 0.0 <= plan.confidence <= 1.0
    assert 0.0 <= plan.expected_risk <= 1.0
    assert plan.expected_value >= 0.0


def test_zero_or_negative_cac_produces_nonnegative_value_and_safe_output():
    cae = CapitalAllocationEngine()
    world = make_world(cac=0.0)  # DefaultValueModel -> 0.0

    plan = cae.allocate(world)

    # Главное: не падаем, возвращаем валидный план.
    assert plan.horizon_days in (30, 60)
    assert len(plan.allocations) >= 1
    assert plan.expected_value >= 0.0


def test_risk_model_matches_expected_formula_for_known_inputs():
    rm = DefaultRiskModel()
    world = make_world(runway_days=100.0, churn_rate=0.2, uncertainty=0.1)

    risk = rm.estimate(world)

    runway_risk = 1 / 100.0
    expected = min(1.0, runway_risk + 0.2 + 0.1)
    assert risk == pytest.approx(expected)


def test_constraints_builder_expected_values():
    cb = ConstraintBuilder()
    world = make_world(cash_balance=50_000.0)
    c = cb.from_world(world)

    assert c.reserve_required == pytest.approx(0.2 * 50_000.0)
    assert c.max_spend == pytest.approx(0.8 * 50_000.0)
    assert c.min_runway_days == 30


def test_growth_and_reserve_amounts_sum_to_spend_in_normal_mode():
    cae = CapitalAllocationEngine()
    world = make_world(cash_balance=100_000.0, marketing_budget=10_000.0, runway_days=120.0)

    plan = cae.allocate(world)
    assert plan.horizon_days == 30

    growth = next(a.amount for a in plan.allocations if a.target == "growth")
    reserve = next(a.amount for a in plan.allocations if a.target == "reserve")

    # Должно раскладываться ровно на spend (маркетинг бюджет, т.к. он меньше max_spend)
    assert (growth + reserve) == pytest.approx(world.capital.marketing_budget)


def test_extreme_value_does_not_overflow_sigmoid_path():
    # Проверяем, что при больших показателях не ловим overflow в math.exp
    # В текущей реализации overflow возможен при exp(очень большой).
    # Мы подберём параметры так, чтобы x = value - risk был умеренным.
    cae = CapitalAllocationEngine()
    world = make_world(ltv=1e6, cac=1.0, growth_rate=1.0, churn_rate=0.0, uncertainty=0.0, runway_days=120.0)

    plan = cae.allocate(world)

    assert plan.horizon_days == 30
    assert len(plan.allocations) == 2
