# tests/test_survival_controller_fuzz_invariants.py
#
# “Боевой” fuzz + инварианты:
# - CRITICAL никогда не может allow_execution=True
# - SAFE всегда включает trigger_rollback + trigger_safe_offers
# - DEGRADED/NORMAL никогда не включают rollback/safe_offers
#
# Запуск:
#   pytest -q
#
# Если hypothesis не установлен:
#   pip install hypothesis

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from survival.controller import (
    MetricsProvider,
    SurvivalConfig,
    SurvivalController,
    SurvivalMetrics,
    SurvivalMode,
)

hypothesis = pytest.importorskip("hypothesis")
st = pytest.importorskip("hypothesis.strategies")
given = hypothesis.given
settings = hypothesis.settings
HealthCheck = hypothesis.HealthCheck


@dataclass
class StubMetricsProvider(MetricsProvider):
    _metrics: SurvivalMetrics

    def set(self, metrics: SurvivalMetrics) -> None:
        self._metrics = metrics

    def get_metrics(self) -> SurvivalMetrics:
        return self._metrics


# Чтобы не ловить NaN/Inf + не уходить в совсем бессмысленные диапазоны
finite_float = st.floats(allow_nan=False, allow_infinity=False, width=64)


# “Адекватные” диапазоны (но с возможностью "сломать" систему)
cashflow_st = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
rate_st = st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False)  # допускаем "кривые" значения
health_st = st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False)


metrics_st = st.builds(
    SurvivalMetrics,
    cashflow=cashflow_st,
    churn_rate=rate_st,
    error_rate=rate_st,
    runtime_alive=st.booleans(),
    policy_health=health_st,
)


@settings(
    max_examples=int(os.getenv('HYPOTHESIS_MAX_EXAMPLES', '800')),

    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(metrics_st)
def test_fuzz_mode_invariants_hold(m: SurvivalMetrics) -> None:
    provider = StubMetricsProvider(m)
    ctrl = SurvivalController(provider, config=SurvivalConfig())

    v = ctrl.evaluate()

    # 1) CRITICAL → всегда запрещает execution
    if v.mode is SurvivalMode.CRITICAL:
        assert v.allow_execution is False

    # 2) SAFE → всегда включает rollback + safe_offers
    if v.mode is SurvivalMode.SAFE:
        assert v.allow_execution is True
        assert v.trigger_rollback is True
        assert v.trigger_safe_offers is True

    # 3) NORMAL/DEGRADED → не должны включать rollback / safe offers
    if v.mode in (SurvivalMode.NORMAL, SurvivalMode.DEGRADED):
        assert v.allow_execution is True
        assert v.trigger_rollback is False
        assert v.trigger_safe_offers is False


@settings(
    max_examples=int(os.getenv('HYPOTHESIS_MAX_EXAMPLES', '800')),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(metrics_st)
def test_runtime_dead_has_priority_over_everything(m: SurvivalMetrics) -> None:
    """
    Приоритет: runtime_dead должен перебивать любые другие условия.
    """
    provider = StubMetricsProvider(
        SurvivalMetrics(
            cashflow=m.cashflow,
            churn_rate=m.churn_rate,
            error_rate=m.error_rate,
            runtime_alive=False,  # forced
            policy_health=m.policy_health,
        )
    )
    ctrl = SurvivalController(provider, config=SurvivalConfig())

    v = ctrl.evaluate()
    assert v.mode is SurvivalMode.CRITICAL
    assert v.allow_execution is False
    assert v.reason == "runtime_dead"


@settings(
    max_examples=int(os.getenv('HYPOTHESIS_MAX_EXAMPLES', '800')),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    churn=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    err=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    health=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_exact_threshold_behavior_is_consistent(churn: float, err: float, health: float) -> None:
    """
    Проверка границ:
    - SAFE триггерится только при строгом превышении (> max) или строгом падении (< min).
    - На ровно границе SAFE не должен сработать (но churn на границе может дать DEGRADED).
    """
    cfg = SurvivalConfig(
        min_cashflow=0.0,
        max_churn=0.25,
        max_error_rate=0.15,
        min_policy_health=0.4,
        degraded_churn_ratio=0.7,
    )
    provider = StubMetricsProvider(
        SurvivalMetrics(
            cashflow=0.0,
            churn_rate=cfg.max_churn,          # exactly boundary
            error_rate=cfg.max_error_rate,     # exactly boundary
            runtime_alive=True,
            policy_health=cfg.min_policy_health,  # exactly boundary
        )
    )
    ctrl = SurvivalController(provider, config=cfg)

    v = ctrl.evaluate()

    # SAFE не должен сработать на равенстве
    assert v.mode is not SurvivalMode.SAFE

    # churn==max_churn всегда > max_churn*ratio (если ratio<1), значит DEGRADED ожидаем.
    assert v.mode is SurvivalMode.DEGRADED
    assert v.reason == "churn_warning"
