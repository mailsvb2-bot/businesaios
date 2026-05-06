from __future__ import annotations

"""Security anomaly detector.

Only scores deviations from baseline. It never issues executable actions.
"""

from dataclasses import dataclass, field
from typing import Mapping

from security.behavioral_baseline import BehavioralBaseline


CANON_SECURITY_ANOMALY_DETECTOR = True


@dataclass(frozen=True)
class AnomalyVerdict:
    anomalous: bool
    score: float
    reason: str
    observed_value: float
    mean: float | None = None
    stddev: float | None = None
    z_score: float | None = None
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass
class AnomalyDetector:
    baseline: BehavioralBaseline = field(default_factory=BehavioralBaseline)
    min_samples: int = 5
    z_score_threshold: float = 3.0
    extreme_multiplier: float = 2.5

    def score(self, *, key: str, observed_value: float) -> AnomalyVerdict:
        try:
            snapshot = self.baseline.snapshot(key)
        except KeyError:
            return AnomalyVerdict(
                anomalous=False,
                score=0.0,
                reason='baseline_missing',
                observed_value=float(observed_value),
                labels={'key': str(key)},
            )
        if snapshot.count < int(self.min_samples):
            return AnomalyVerdict(
                anomalous=False,
                score=0.0,
                reason='baseline_insufficient',
                observed_value=float(observed_value),
                mean=snapshot.mean,
                stddev=snapshot.stddev,
                labels={'key': str(key), 'sample_count': str(snapshot.count)},
            )
        z_score = abs(snapshot.z_score(float(observed_value)))
        range_span = max(1.0, snapshot.maximum - snapshot.minimum)
        out_of_range = 0.0
        if observed_value > snapshot.maximum:
            out_of_range = (float(observed_value) - snapshot.maximum) / range_span
        elif observed_value < snapshot.minimum:
            out_of_range = (snapshot.minimum - float(observed_value)) / range_span
        normalized_z = min(1.0, z_score / max(1.0, self.z_score_threshold * self.extreme_multiplier))
        normalized_range = min(1.0, out_of_range / self.extreme_multiplier)
        score = max(normalized_z, normalized_range)
        anomalous = z_score >= float(self.z_score_threshold) or out_of_range >= float(self.extreme_multiplier)
        return AnomalyVerdict(
            anomalous=anomalous,
            score=score,
            reason='anomaly_detected' if anomalous else 'within_baseline',
            observed_value=float(observed_value),
            mean=snapshot.mean,
            stddev=snapshot.stddev,
            z_score=z_score,
            labels={'key': str(key), 'sample_count': str(snapshot.count)},
        )


__all__ = [
    'AnomalyDetector',
    'AnomalyVerdict',
    'CANON_SECURITY_ANOMALY_DETECTOR',
]
