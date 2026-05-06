"""Survival controller (canonical).

Last safety layer before irreversible side-effects.
This module is intentionally small and deterministic.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


logger = logging.getLogger("survival.controller")


class SurvivalMode(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    SAFE = "safe"
    CRITICAL = "critical"


class MetricsProvider(Protocol):
    def get_metrics(self) -> "SurvivalMetrics": ...


@dataclass(frozen=True)
class SurvivalMetrics:
    cashflow: float
    churn_rate: float
    error_rate: float
    runtime_alive: bool
    policy_health: float


@dataclass(frozen=True)
class SurvivalVerdict:
    allow_execution: bool
    mode: SurvivalMode
    reason: Optional[str] = None
    trigger_rollback: bool = False
    trigger_safe_offers: bool = False


@dataclass(frozen=True)
class SurvivalConfig:
    min_cashflow: float = 0.0
    max_churn: float = 0.25
    max_error_rate: float = 0.15
    min_policy_health: float = 0.4
    degraded_churn_ratio: float = 0.7



class _DefaultMetricsProvider:
    """Fallback provider used by tests/small harnesses."""

    def get_metrics(self) -> "SurvivalMetrics":
        return SurvivalMetrics(
            cashflow=1.0,
            churn_rate=0.0,
            error_rate=0.0,
            runtime_alive=True,
            policy_health=1.0,
        )

class SurvivalController:
    """Thread-safe deterministic evaluator for survival state."""

    def __init__(self, metrics_provider: MetricsProvider | None = None, config: SurvivalConfig | None = None) -> None:
        if metrics_provider is None:
            metrics_provider = _DefaultMetricsProvider()
        self._metrics_provider = metrics_provider
        self._config = config or SurvivalConfig()
        self._lock = threading.Lock()
        self._last_verdict: Optional[SurvivalVerdict] = None
        self._last_logged_key: Optional[tuple] = None
        self._last_logged_ts: float = 0.0

    def evaluate(self) -> SurvivalVerdict:
        m = self._metrics_provider.get_metrics()
        cfg = self._config

        # Priority order: runtime death -> negative cashflow -> instability -> warning band -> normal
        if not bool(m.runtime_alive):
            verdict = SurvivalVerdict(
                allow_execution=False,
                mode=SurvivalMode.CRITICAL,
                reason="runtime_dead",
                trigger_rollback=True,
                trigger_safe_offers=True,
            )
        elif float(m.cashflow) < 0.0:
            verdict = SurvivalVerdict(
                allow_execution=False,
                mode=SurvivalMode.CRITICAL,
                reason="negative_cashflow",
                trigger_rollback=True,
                trigger_safe_offers=True,
            )
        elif (
            float(m.churn_rate) > float(cfg.max_churn)
            or float(m.error_rate) > float(cfg.max_error_rate)
            or float(m.policy_health) < float(cfg.min_policy_health)
        ):
            verdict = SurvivalVerdict(
                allow_execution=True,
                mode=SurvivalMode.SAFE,
                reason="instability_detected",
                trigger_rollback=True,
                trigger_safe_offers=True,
            )
        else:
            churn_warn = float(cfg.max_churn) * float(cfg.degraded_churn_ratio)
            # Strict boundaries: warning is triggered at >= warn band.
            if float(m.churn_rate) >= churn_warn:
                verdict = SurvivalVerdict(
                    allow_execution=True,
                    mode=SurvivalMode.DEGRADED,
                    reason="churn_warning",
                    trigger_rollback=False,
                    trigger_safe_offers=False,
                )
            else:
                verdict = SurvivalVerdict(
                    allow_execution=True,
                    mode=SurvivalMode.NORMAL,
                    reason=None,
                    trigger_rollback=False,
                    trigger_safe_offers=False,
                )

        with self._lock:
            self._last_verdict = verdict
            self._log_transition_if_needed(verdict, m)
        return verdict

    def last_verdict(self) -> Optional[SurvivalVerdict]:
        with self._lock:
            return self._last_verdict

    def _log_transition_if_needed(self, verdict: SurvivalVerdict, metrics: SurvivalMetrics) -> None:
        key = (verdict.mode, verdict.reason, verdict.allow_execution, verdict.trigger_rollback, verdict.trigger_safe_offers)
        now = time.time()
        if self._last_logged_key == key and (now - self._last_logged_ts) < 30.0:
            return
        self._last_logged_key = key
        self._last_logged_ts = now

        # Emit structured-ish log with extra attributes (tests rely on this).
        logger.info(
            "survival verdict",
            extra={
                "mode": verdict.mode.value,
                "reason": verdict.reason,
                "allow_execution": verdict.allow_execution,
                "rollback": verdict.trigger_rollback,
                "safe_offers": verdict.trigger_safe_offers,
                "runtime_alive": bool(metrics.runtime_alive),
            },
        )


__all__ = [
    "SurvivalMode",
    "SurvivalMetrics",
    "SurvivalVerdict",
    "SurvivalConfig",
    "MetricsProvider",
    "SurvivalController",
]
