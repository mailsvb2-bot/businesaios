from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.optimization.adaptation_metrics import clamp, safe_float


NOISE_GUARD_SCHEMA_VERSION = 2


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True)
class NoiseGuardConfig:
    min_confidence: float = 0.45
    max_latency_ms: float = 180_000.0
    max_cost_outlier_ratio: float = 8.0
    duplicate_window_size: int = 50
    min_cost_baseline_samples: int = 5
    min_latency_baseline_samples: int = 5


@dataclass(frozen=True)
class NoiseGuardDecision:
    accepted: bool
    reason: str
    confidence: float
    anomaly_score: float
    duplicate: bool = False


@dataclass
class NoiseMemory:
    recent_fingerprints: list[str] = field(default_factory=list)
    recent_costs: list[float] = field(default_factory=list)
    recent_latencies_ms: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'recent_fingerprints': list(self.recent_fingerprints[-200:]),
            'recent_costs': [float(v) for v in self.recent_costs[-200:]],
            'recent_latencies_ms': [float(v) for v in self.recent_latencies_ms[-200:]],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'NoiseMemory':
        return cls(
            recent_fingerprints=[_safe_text(x) for x in (payload.get('recent_fingerprints') or []) if _safe_text(x)][-200:],
            recent_costs=[max(0.0, safe_float(x)) for x in (payload.get('recent_costs') or [])][-200:],
            recent_latencies_ms=[max(0.0, safe_float(x)) for x in (payload.get('recent_latencies_ms') or [])][-200:],
        )

    def remember(self, *, fingerprint: str, cost: float, latency_ms: float, window_size: int) -> None:
        window_size = max(1, int(window_size))
        if fingerprint:
            self.recent_fingerprints.append(fingerprint)
            self.recent_fingerprints[:] = self.recent_fingerprints[-window_size:]
        self.recent_costs.append(max(0.0, cost))
        self.recent_costs[:] = self.recent_costs[-window_size:]
        self.recent_latencies_ms.append(max(0.0, latency_ms))
        self.recent_latencies_ms[:] = self.recent_latencies_ms[-window_size:]


class FeedbackNoiseGuard:
    def __init__(self, *, config: NoiseGuardConfig | None = None) -> None:
        self._config = config or NoiseGuardConfig()

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    def evaluate(self, *, observation: Mapping[str, Any], memory: NoiseMemory | None = None) -> NoiseGuardDecision:
        payload = _safe_dict(observation)
        confidence = clamp(safe_float(payload.get('verification_confidence'), default=0.0))
        latency_ms = max(0.0, safe_float(payload.get('latency_ms'), default=0.0))
        cost = max(0.0, safe_float(payload.get('cost'), default=0.0))
        fingerprint = _safe_text(payload.get('fingerprint'))
        identity_complete = bool(payload.get('identity_complete', True))
        memory = memory or NoiseMemory()
        duplicate = bool(fingerprint and fingerprint in memory.recent_fingerprints)
        if not identity_complete:
            return NoiseGuardDecision(False, 'invalid_identity', confidence, 1.0)
        if duplicate:
            return NoiseGuardDecision(False, 'duplicate_feedback', confidence, 1.0, True)
        if confidence < self._config.min_confidence:
            return NoiseGuardDecision(False, 'low_verification_confidence', confidence, clamp(1.0 - confidence))
        if latency_ms > self._config.max_latency_ms:
            overflow = (latency_ms - self._config.max_latency_ms) / max(1.0, self._config.max_latency_ms)
            return NoiseGuardDecision(False, 'latency_outlier', confidence, clamp(overflow))
        if len(memory.recent_costs) >= self._config.min_cost_baseline_samples:
            median_cost = self._median(memory.recent_costs)
            if median_cost > 0.0 and cost > (median_cost * self._config.max_cost_outlier_ratio):
                overflow = (cost - (median_cost * self._config.max_cost_outlier_ratio)) / max(1.0, median_cost * self._config.max_cost_outlier_ratio)
                return NoiseGuardDecision(False, 'cost_outlier', confidence, clamp(overflow))
        anomaly = 0.0
        if len(memory.recent_latencies_ms) >= self._config.min_latency_baseline_samples:
            median_latency = self._median(memory.recent_latencies_ms)
            if median_latency > 0.0 and latency_ms > median_latency:
                anomaly = clamp((latency_ms - median_latency) / max(1.0, median_latency))
        return NoiseGuardDecision(True, 'accepted', confidence, anomaly)

    def commit(self, *, observation: Mapping[str, Any], memory: NoiseMemory) -> NoiseMemory:
        payload = _safe_dict(observation)
        memory.remember(
            fingerprint=_safe_text(payload.get('fingerprint')),
            cost=max(0.0, safe_float(payload.get('cost'), default=0.0)),
            latency_ms=max(0.0, safe_float(payload.get('latency_ms'), default=0.0)),
            window_size=max(1, int(self._config.duplicate_window_size)),
        )
        return memory


__all__ = ['FeedbackNoiseGuard', 'NoiseGuardConfig', 'NoiseGuardDecision', 'NoiseMemory', 'NOISE_GUARD_SCHEMA_VERSION']
