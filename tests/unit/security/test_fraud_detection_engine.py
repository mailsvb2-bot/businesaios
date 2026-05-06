from __future__ import annotations

from security.behavioral_baseline import BehavioralBaseline
from security.anomaly_detector import AnomalyDetector
from security.fraud_detection_engine import FraudDetectionEngine


def test_fraud_engine_does_not_penalize_trusted_customer() -> None:
    baseline = BehavioralBaseline()
    for value in (10, 11, 10, 9, 11, 10):
        baseline.observe(key='tenant-1:request_rate', value=value)
    engine = FraudDetectionEngine(anomaly_detector=AnomalyDetector(baseline=baseline))
    verdict = engine.evaluate(
        tenant_id='tenant-1',
        signals={
            'request_rate': 10,
            'existing_customer_trusted': True,
        },
    )
    assert verdict.allowed is True
    assert verdict.risk_score < 0.1


def test_fraud_engine_blocks_extreme_signal() -> None:
    baseline = BehavioralBaseline()
    for value in (10, 10, 10, 11, 9, 10):
        baseline.observe(key='tenant-1:request_rate', value=value)
    engine = FraudDetectionEngine(
        anomaly_detector=AnomalyDetector(baseline=baseline, z_score_threshold=2.0),
        hard_fail_signal_threshold=0.95,
    )
    verdict = engine.evaluate(
        tenant_id='tenant-1',
        signals={'request_rate': 1000.0, 'spend_ratio': 1.0},
    )
    assert verdict.allowed is False
    assert verdict.reason in {'hard_fail_signal', 'fraud_risk_denied'}
