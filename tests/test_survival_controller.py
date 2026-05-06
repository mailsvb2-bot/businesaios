import logging
from dataclasses import dataclass
from typing import Optional

import pytest

from survival.controller import (
    MetricsProvider,
    SurvivalConfig,
    SurvivalController,
    SurvivalMetrics,
    SurvivalMode,
    SurvivalVerdict,
)


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


def assert_verdict(
    v: SurvivalVerdict,
    *,
    allow_execution: bool,
    mode: SurvivalMode,
    reason: Optional[str],
    trigger_rollback: bool,
    trigger_safe_offers: bool,
) -> None:
    assert v.allow_execution is allow_execution
    assert v.mode is mode
    assert v.reason == reason
    assert v.trigger_rollback is trigger_rollback
    assert v.trigger_safe_offers is trigger_safe_offers


def test_normal_mode() -> None:
    provider = StubMetricsProvider(m())
    ctrl = SurvivalController(provider)

    v = ctrl.evaluate()

    assert_verdict(
        v,
        allow_execution=True,
        mode=SurvivalMode.NORMAL,
        reason=None,
        trigger_rollback=False,
        trigger_safe_offers=False,
    )
    assert ctrl.last_verdict() == v


def test_critical_when_runtime_dead() -> None:
    provider = StubMetricsProvider(m(runtime_alive=False))
    ctrl = SurvivalController(provider)

    v = ctrl.evaluate()

    assert_verdict(
        v,
        allow_execution=False,
        mode=SurvivalMode.CRITICAL,
        reason="runtime_dead",
        trigger_rollback=True,
        trigger_safe_offers=True,
    )


def test_critical_when_negative_cashflow() -> None:
    provider = StubMetricsProvider(m(cashflow=-0.01))
    ctrl = SurvivalController(provider)

    v = ctrl.evaluate()

    assert_verdict(
        v,
        allow_execution=False,
        mode=SurvivalMode.CRITICAL,
        reason="negative_cashflow",
        trigger_rollback=True,
        trigger_safe_offers=True,
    )


def test_safe_when_churn_exceeds_threshold() -> None:
    cfg = SurvivalConfig(max_churn=0.25)
    provider = StubMetricsProvider(m(churn_rate=0.251))
    ctrl = SurvivalController(provider, config=cfg)

    v = ctrl.evaluate()

    assert_verdict(
        v,
        allow_execution=True,
        mode=SurvivalMode.SAFE,
        reason="instability_detected",
        trigger_rollback=True,
        trigger_safe_offers=True,
    )


def test_safe_when_error_rate_exceeds_threshold() -> None:
    cfg = SurvivalConfig(max_error_rate=0.15)
    provider = StubMetricsProvider(m(error_rate=0.151))
    ctrl = SurvivalController(provider, config=cfg)

    v = ctrl.evaluate()

    assert_verdict(
        v,
        allow_execution=True,
        mode=SurvivalMode.SAFE,
        reason="instability_detected",
        trigger_rollback=True,
        trigger_safe_offers=True,
    )


def test_safe_when_policy_health_below_threshold() -> None:
    cfg = SurvivalConfig(min_policy_health=0.4)
    provider = StubMetricsProvider(m(policy_health=0.399))
    ctrl = SurvivalController(provider, config=cfg)

    v = ctrl.evaluate()

    assert_verdict(
        v,
        allow_execution=True,
        mode=SurvivalMode.SAFE,
        reason="instability_detected",
        trigger_rollback=True,
        trigger_safe_offers=True,
    )


def test_degraded_when_churn_above_warning_band_but_below_safe() -> None:
    cfg = SurvivalConfig(max_churn=0.25, degraded_churn_ratio=0.7)  # warning > 0.175
    provider = StubMetricsProvider(m(churn_rate=0.176))
    ctrl = SurvivalController(provider, config=cfg)

    v = ctrl.evaluate()

    assert_verdict(
        v,
        allow_execution=True,
        mode=SurvivalMode.DEGRADED,
        reason="churn_warning",
        trigger_rollback=False,
        trigger_safe_offers=False,
    )


def test_threshold_boundaries_are_strict() -> None:
    cfg = SurvivalConfig(
        min_cashflow=0.0,
        max_churn=0.25,
        max_error_rate=0.15,
        min_policy_health=0.4,
        degraded_churn_ratio=0.7,
    )
    provider = StubMetricsProvider(
        m(
            cashflow=0.0,
            churn_rate=0.25,
            error_rate=0.15,
            policy_health=0.4,
        )
    )
    ctrl = SurvivalController(provider, config=cfg)

    v = ctrl.evaluate()

    assert v.mode is SurvivalMode.DEGRADED
    assert v.allow_execution is True
    assert v.reason == "churn_warning"


def test_last_verdict_is_updated_on_each_evaluate() -> None:
    provider = StubMetricsProvider(m())
    ctrl = SurvivalController(provider)

    v1 = ctrl.evaluate()
    assert ctrl.last_verdict() == v1

    provider.set(m(runtime_alive=False))
    v2 = ctrl.evaluate()
    assert ctrl.last_verdict() == v2
    assert v1 != v2


def test_logs_emitted(caplog: pytest.LogCaptureFixture) -> None:
    provider = StubMetricsProvider(m(runtime_alive=False))
    ctrl = SurvivalController(provider)

    with caplog.at_level(logging.INFO, logger="survival.controller"):
        v = ctrl.evaluate()

    assert any(rec.levelname == "INFO" for rec in caplog.records)

    rec = next(rec for rec in caplog.records if rec.name == "survival.controller")
    assert getattr(rec, "mode") == v.mode.value
    assert getattr(rec, "reason") == v.reason
    assert getattr(rec, "allow_execution") == v.allow_execution
    assert getattr(rec, "rollback") == v.trigger_rollback
    assert getattr(rec, "safe_offers") == v.trigger_safe_offers
    assert getattr(rec, "runtime_alive") is False
