from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from contracts.platforms.market_intelligence_advanced_contract import UnifiedSignal


CANON_MARKET_INTELLIGENCE_SCORING = True


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_datetime(value: str | None) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


@dataclass(frozen=True)
class SignalScore:
    entity_id: str
    structured_importance: float
    confidence: float
    strength: float
    freshness: float
    frequency: float
    signals_count: int

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            'entity_id': self.entity_id,
            'structured_importance': self.structured_importance,
            'confidence': self.confidence,
            'strength': self.strength,
            'freshness': self.freshness,
            'frequency': self.frequency,
            'signals_count': self.signals_count,
        }


class EvidenceScoringEngine:
    def score(self, signals: Iterable[UnifiedSignal]) -> tuple[SignalScore, ...]:
        grouped: dict[str, list[UnifiedSignal]] = {}
        for signal in signals:
            grouped.setdefault(signal.entity_id, []).append(signal)
        scores: list[SignalScore] = []
        for entity_id, bucket in grouped.items():
            count = max(1, len(bucket))
            confidence = min(sum(item.confidence for item in bucket) / count, 1.0)
            strength = min(sum(item.strength for item in bucket) / count, 1.0)
            freshness = min(sum(self._freshness_value(item.observed_at) for item in bucket) / count, 1.0)
            frequency = min(len({item.provider for item in bucket}) / 5.0 + sum(item.frequency for item in bucket) / count / 2.0, 1.0)
            structured_importance = min((confidence * 0.35) + (strength * 0.30) + (freshness * 0.20) + (frequency * 0.15), 1.0)
            scores.append(SignalScore(entity_id=entity_id, structured_importance=structured_importance, confidence=confidence, strength=strength, freshness=freshness, frequency=frequency, signals_count=count))
        return tuple(sorted(scores, key=lambda item: (-item.structured_importance, item.entity_id)))

    def _freshness_value(self, observed_at: str) -> float:
        dt = _safe_datetime(observed_at)
        if dt is None:
            return 0.25
        delta_hours = max(0.0, (_utc_now() - dt.astimezone(UTC)).total_seconds() / 3600.0)
        if delta_hours <= 24:
            return 1.0
        if delta_hours <= 24 * 7:
            return 0.8
        if delta_hours <= 24 * 30:
            return 0.6
        if delta_hours <= 24 * 90:
            return 0.4
        return 0.2


__all__ = ['CANON_MARKET_INTELLIGENCE_SCORING', 'EvidenceScoringEngine', 'SignalScore']
