from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping

from contracts.platforms.market_intelligence_advanced_contract import UnifiedSignal
from execution.market_intelligence_advanced_models import EntityCandidate


CANON_MARKET_INTELLIGENCE_SIGNAL_FUSION = True


def _normalize_text(value: object) -> str:
    return ' '.join(''.join(ch.lower() if ch.isalnum() else ' ' for ch in str(value or '')).split())


def _token_set(value: object) -> set[str]:
    return {token for token in _normalize_text(value).split() if token}


@dataclass(frozen=True)
class EntityResolution:
    entity_id: str
    confidence: float
    reason: str
    merge_allowed: bool
    temporal_snapshot_at: str


@dataclass(frozen=True)
class FusionPolicy:
    merge_threshold: float = 0.82
    hard_title_conflict_threshold: float = 0.35


class EntityResolver:
    def __init__(self, policy: FusionPolicy | None = None) -> None:
        self.policy = policy or FusionPolicy()

    def resolve(self, *, candidate: EntityCandidate, records: Iterable[Mapping[str, Any]]) -> EntityResolution:
        aliases = {candidate.title, *candidate.aliases}
        best_score = 0.0
        best_reason = 'no_match'
        for row in records:
            title = str(row.get('title') or row.get('name') or row.get('headline') or '').strip()
            if not title:
                continue
            score = max(self._score(alias, title) for alias in aliases if alias)
            if score > best_score:
                best_score = score
                best_reason = f'title_match:{title[:48]}'
        if best_score < self.policy.hard_title_conflict_threshold:
            best_reason = 'anti_overmerge_triggered'
        return EntityResolution(entity_id=candidate.entity_id, confidence=max(0.0, min(best_score, 1.0)), reason=best_reason, merge_allowed=best_score >= self.policy.merge_threshold, temporal_snapshot_at=datetime.now(UTC).isoformat())

    def _score(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        left_tokens = _token_set(left)
        right_tokens = _token_set(right)
        overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
        ratio = SequenceMatcher(a=_normalize_text(left), b=_normalize_text(right)).ratio()
        return max(overlap, ratio)


class SignalAggregator:
    def aggregate(self, signals: Iterable[UnifiedSignal]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for signal in signals:
            bucket = grouped.setdefault(signal.entity_id, {
                'entity_id': signal.entity_id,
                'entity_kind': signal.entity_kind,
                'providers': set(),
                'source_families': set(),
                'signal_kinds': set(),
                'confidence': 0.0,
                'strength': 0.0,
                'freshness': 0.0,
                'frequency': 0.0,
                'signals_count': 0,
                'payloads': [],
                'temporal_snapshots': [],
            })
            bucket['providers'].add(signal.provider)
            bucket['source_families'].add(signal.source_family)
            bucket['signal_kinds'].add(signal.signal_kind)
            bucket['confidence'] = max(bucket['confidence'], float(signal.confidence))
            bucket['strength'] += float(signal.strength)
            bucket['freshness'] = max(bucket['freshness'], float(signal.freshness))
            bucket['frequency'] += float(signal.frequency)
            bucket['signals_count'] += 1
            bucket['payloads'].append(dict(signal.payload))
            bucket['temporal_snapshots'].append({'provider': signal.provider, 'source_family': signal.source_family, 'signal_kind': signal.signal_kind, 'observed_at': str(signal.payload.get('observed_at') or '')})
        for bucket in grouped.values():
            count = max(1, int(bucket['signals_count']))
            bucket['strength'] = min(bucket['strength'] / count, 1.0)
            bucket['frequency'] = min(bucket['frequency'] / count, 1.0)
            bucket['providers'] = sorted(bucket['providers'])
            bucket['source_families'] = sorted(bucket['source_families'])
            bucket['signal_kinds'] = sorted(bucket['signal_kinds'])
        return grouped


__all__ = ['CANON_MARKET_INTELLIGENCE_SIGNAL_FUSION', 'EntityResolution', 'EntityResolver', 'FusionPolicy', 'SignalAggregator']
