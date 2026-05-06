# tests/test_survival_controller_hard.py
#
# "Жёсткие" тесты:
# 1) property-based (Hypothesis) на инварианты
# 2) многопоточность (stress) на отсутствие гонок/исключений
#
# Запуск:
#   pytest -q
#
# Если hypothesis не установлен:
#   pip install hypothesis

from __future__ import annotations

import threading
from dataclasses import dataclass

import pytest

from survival.controller import (
    MetricsProvider,
    SurvivalConfig,
    SurvivalController,
    SurvivalMetrics,
    SurvivalMode,
)

# -----------------------------
# Shared test helpers
# -----------------------------


@dataclass
class StubMetricsProvider(MetricsProvider):
    _metrics: SurvivalMetrics

    def set(self, metrics: SurvivalMetrics) -> None:
        self._metrics = metrics

    def get_metrics(self) -> SurvivalMetrics:
        return self._metrics


def m(
    cashflow: float = 10.0,
    churn_rate: float = 0.05,
    error_rate: float = 0.01,
    runtime_alive: bool = True,
    policy_health: float = 0.9,
) -> SurvivalMetrics:
    return SurvivalMetrics(
        cashflow=cashflow,
        churn_rate=churn_rate,
        error_rate=error_rate,
        runtime_alive=runtime_alive,
        policy_health=policy_health,
    )


# ============================================================
# 1) Property-based tests (Hypothesis)
# ============================================================

hypothesis = pytest.importorskip("hypothesis")
st = pytest.importorskip("hypothesis.strategies")
given = hypothesis.given
settings = hypothesis.settings
HealthCheck = hypothesis.HealthCheck


# Стратегии: держим их “разумными” (без NaN/inf), чтобы не плодить ложные ошибки.
finite_float = st.floats(allow_nan=False, allow_infinity=False, width=64)

metrics_strategy = st.builds(
    SurvivalMetrics,
    cashflow=finite_float,
    churn_rate=finite_float,
    error_rate=finite_float,
    runtime_alive=st.booleans(),
    policy_health=finite_float,
)


@settings(
    max_examples=600,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(metrics_strategy)
def test_invariant_runtime_dead_always_critical_and_blocks_execution(sm: SurvivalMetrics) -> None:
    """
    Инвариант: если runtime_alive=False → CRITICAL и allow_execution=False.
    (Независимо от остальных метрик.)
    """
    provider = StubMetricsProvider(sm)
    ctrl = SurvivalController(provider)

    provider.set(
        SurvivalMetrics(
            cashflow=sm.cashflow,
            churn_rate=sm.churn_rate,
            error_rate=sm.error_rate,
            runtime_alive=False,  # forced
            policy_health=sm.policy_health,
        )
    )

    v = ctrl.evaluate()
    assert v.mode is SurvivalMode.CRITICAL
    assert v.allow_execution is False
    assert v.reason == "runtime_dead"
    assert v.trigger_rollback is True
    assert v.trigger_safe_offers is True


@settings(
    max_examples=600,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    cashflow=finite_float,
    churn_rate=finite_float,
    error_rate=finite_float,
    policy_health=finite_float,
)
def test_invariant_negative_cashflow_always_critical_and_blocks_execution(
    cashflow: float,
    churn_rate: float,
    error_rate: float,
    policy_health: float,
) -> None:
    """
    Инвариант: если cashflow < min_cashflow (по умолчанию 0.0) → CRITICAL и allow_execution=False.
    """
    provider = StubMetricsProvider(
        SurvivalMetrics(
            cashflow=cashflow,
            churn_rate=churn_rate,
            error_rate=error_rate,
            runtime_alive=True,
            policy_health=policy_health,
        )
    )
    ctrl = SurvivalController(provider, config=SurvivalConfig(min_cashflow=0.0))

    provider.set(
        SurvivalMetrics(
            cashflow=-abs(cashflow) - 1e-12,  # guaranteed < 0
            churn_rate=churn_rate,
            error_rate=error_rate,
            runtime_alive=True,
            policy_health=policy_health,
        )
    )

    v = ctrl.evaluate()
    assert v.mode is SurvivalMode.CRITICAL
    assert v.allow_execution is False
    assert v.reason == "negative_cashflow"
    assert v.trigger_rollback is True
    assert v.trigger_safe_offers is True


# ============================================================
# 2) Threading / race stress test
# ============================================================

def test_thread_safety_stress_evaluate_and_last_verdict() -> None:
    """
    Цель: доказать отсутствие гонок/исключений и корректную работу lock.

    Сценарий:
    - Несколько потоков параллельно:
      - мутируют provider.set(...)
      - вызывают ctrl.evaluate()
      - читают ctrl.last_verdict()
    - Проверяем: нет исключений, last_verdict всегда либо None, либо валидный объект.
    """
    provider = StubMetricsProvider(m())
    ctrl = SurvivalController(provider, config=SurvivalConfig())

    threads = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(16)  # 15 workers + main

    def worker(idx: int) -> None:
        try:
            barrier.wait()
            # Небольшой "мелтдаун" сценарий: часть потоков периодически делает runtime_dead,
            # часть делает SAFE/DEGRADED/CRITICAL по cashflow, часть — NORMAL.
            for i in range(500):
                if (idx + i) % 37 == 0:
                    provider.set(m(runtime_alive=False))
                elif (idx + i) % 41 == 0:
                    provider.set(m(cashflow=-0.01))
                elif (idx + i) % 11 == 0:
                    provider.set(m(churn_rate=0.30))
                elif (idx + i) % 7 == 0:
                    provider.set(m(churn_rate=0.20))
                else:
                    provider.set(m())

                v = ctrl.evaluate()
                lv = ctrl.last_verdict()

                # last_verdict должен быть либо None (теоретически только до первой evaluate),
                # либо SurvivalVerdict с корректными полями.
                assert lv is None or hasattr(lv, "mode")
                assert hasattr(v, "allow_execution")
                assert v.mode in (
                    SurvivalMode.NORMAL,
                    SurvivalMode.DEGRADED,
                    SurvivalMode.SAFE,
                    SurvivalMode.CRITICAL,
                )
        except BaseException as e:
            errors.append(e)

    for t in range(15):
        threads.append(threading.Thread(target=worker, args=(t,), daemon=True))

    for th in threads:
        th.start()

    # синхро-старт
    barrier.wait()

    for th in threads:
        th.join(timeout=10)

    # Если поток завис — это уже плохо.
    assert all(not th.is_alive() for th in threads), "Thread(s) stuck: possible deadlock/hang"

    # Если что-то упало — покажем первую ошибку.
    if errors:
        raise errors[0]
