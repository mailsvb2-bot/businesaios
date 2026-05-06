from __future__ import annotations

"""Fraud and abuse signal combiner.

This module does not choose business actions. It only produces risk verdicts
for operator review / fail-closed gating.
"""

import math
from dataclasses import dataclass, field
from typing import Mapping

from security.anomaly_detector import AnomalyDetector, AnomalyVerdict


CANON_SECURITY_FRAUD_DETECTION_ENGINE = True


@dataclass(frozen=True)
class FraudVerdict:
    allowed: bool
    risk_score: float
    requires_operator: bool
    reason: str
    triggered_signals: tuple[str, ...] = ()
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass
class FraudDetectionEngine:
    anomaly_detector: AnomalyDetector = field(default_factory=AnomalyDetector)
    operator_threshold: float = 0.65
    deny_threshold: float = 0.90
    hard_fail_signal_threshold: float = 0.98

    def evaluate(
        self,
        *,
        tenant_id: str,
        signals: Mapping[str, float | int | bool],
    ) -> FraudVerdict:
        normalized = {str(key): value for key, value in dict(signals).items()}
        signal_scores: dict[str, float] = {}
        triggered: list[str] = []

        anomaly_key = f'{tenant_id}:request_rate'
        if 'request_rate' in normalized:
            anomaly_verdict = self.anomaly_detector.score(key=anomaly_key, observed_value=float(normalized['request_rate']))
            self._maybe_add_signal(signal_scores, triggered, 'request_rate_anomaly', anomaly_verdict)

        high_spend = self._clamped_ratio(normalized.get('spend_ratio'))
        if high_spend > 0.0:
            signal_scores['spend_ratio'] = high_spend
            if high_spend >= 0.5:
                triggered.append('spend_ratio')

        new_device = 0.35 if bool(normalized.get('new_device')) else 0.0
        if new_device:
            signal_scores['new_device'] = new_device
            triggered.append('new_device')

        geo_velocity = self._clamped_ratio(normalized.get('geo_velocity_risk'))
        if geo_velocity > 0.0:
            signal_scores['geo_velocity_risk'] = geo_velocity
            if geo_velocity >= 0.4:
                triggered.append('geo_velocity_risk')

        failed_auth_rate = self._clamped_ratio(normalized.get('failed_auth_rate'))
        if failed_auth_rate > 0.0:
            signal_scores['failed_auth_rate'] = failed_auth_rate
            if failed_auth_rate >= 0.3:
                triggered.append('failed_auth_rate')

        trusted_customer = bool(normalized.get('existing_customer_trusted'))
        if trusted_customer:
            signal_scores['trusted_customer_offset'] = -0.15

        combined = self._combine_scores(signal_scores)
        if any(score >= float(self.hard_fail_signal_threshold) for score in signal_scores.values() if score > 0.0):
            return FraudVerdict(
                allowed=False,
                risk_score=1.0,
                requires_operator=True,
                reason='hard_fail_signal',
                triggered_signals=tuple(sorted(set(triggered))),
                labels={k: self._fmt(v) for k, v in signal_scores.items()},
            )
        if combined >= float(self.deny_threshold):
            return FraudVerdict(
                allowed=False,
                risk_score=combined,
                requires_operator=True,
                reason='fraud_risk_denied',
                triggered_signals=tuple(sorted(set(triggered))),
                labels={k: self._fmt(v) for k, v in signal_scores.items()},
            )
        if combined >= float(self.operator_threshold):
            return FraudVerdict(
                allowed=False,
                risk_score=combined,
                requires_operator=True,
                reason='fraud_risk_operator_review',
                triggered_signals=tuple(sorted(set(triggered))),
                labels={k: self._fmt(v) for k, v in signal_scores.items()},
            )
        return FraudVerdict(
            allowed=True,
            risk_score=combined,
            requires_operator=False,
            reason='fraud_risk_within_policy',
            triggered_signals=tuple(sorted(set(triggered))),
            labels={k: self._fmt(v) for k, v in signal_scores.items()},
        )

    @staticmethod
    def _combine_scores(signal_scores: Mapping[str, float]) -> float:
        positive = [max(0.0, min(1.0, score)) for score in signal_scores.values() if score > 0.0]
        dampeners = [abs(score) for score in signal_scores.values() if score < 0.0]
        if not positive:
            base = 0.0
        else:
            base = 1.0 - math.prod(1.0 - score for score in positive)
        for dampener in dampeners:
            base *= max(0.0, 1.0 - min(0.5, dampener))
        return max(0.0, min(1.0, base))

    @staticmethod
    def _clamped_ratio(value: float | int | bool | None) -> float:
        if value is None or isinstance(value, bool):
            return 0.0
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _fmt(value: float) -> str:
        return f'{value:.4f}'

    @classmethod
    def _maybe_add_signal(
        cls,
        signal_scores: dict[str, float],
        triggered: list[str],
        key: str,
        verdict: AnomalyVerdict,
    ) -> None:
        if verdict.score <= 0.0:
            return
        signal_scores[key] = max(0.0, min(1.0, float(verdict.score)))
        if verdict.anomalous:
            triggered.append(key)


__all__ = [
    'CANON_SECURITY_FRAUD_DETECTION_ENGINE',
    'FraudDetectionEngine',
    'FraudVerdict',
]
