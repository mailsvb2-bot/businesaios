from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from contracts.platforms.market_intelligence_advanced_contract import OpportunityEvidence, UnifiedSignal
from execution.market_intelligence_scoring import EvidenceScoringEngine


CANON_MARKET_INTELLIGENCE_OPPORTUNITY_DETECTOR = True


@dataclass
class OpportunityDetector:
    scorer: EvidenceScoringEngine = EvidenceScoringEngine()

    def detect(self, signals: Iterable[UnifiedSignal]) -> tuple[OpportunityEvidence, ...]:
        items = tuple(signals)
        by_entity: dict[str, list[UnifiedSignal]] = {}
        for signal in items:
            by_entity.setdefault(signal.entity_id, []).append(signal)
        scores = {item.entity_id: item for item in self.scorer.score(items)}
        opportunities: list[OpportunityEvidence] = []
        for entity_id, bucket in by_entity.items():
            kinds = Counter(item.signal_kind for item in bucket)
            title = str(bucket[0].payload.get('title') or bucket[0].payload.get('name') or entity_id)
            score = scores.get(entity_id)
            if score is None:
                continue
            if 'demand' in kinds and score.freshness >= 0.7 and score.structured_importance >= 0.65:
                opportunities.append(self._build(bucket[0], 'rising_demand', title, score, ('search or marketplace momentum detected',)))
            if 'complaint' in kinds and kinds['complaint'] >= 2 and score.confidence >= 0.55:
                opportunities.append(self._build(bucket[0], 'repeated_complaints', title, score, ('repeated pain signals detected',)))
            if 'pricing' in kinds and 'competitor' in kinds and score.strength >= 0.55:
                opportunities.append(self._build(bucket[0], 'pricing_gap', title, score, ('pricing and competitor overlap suggests a gap',)))
            if 'competitor' in kinds and len({item.provider for item in bucket}) >= 3 and score.frequency >= 0.55:
                opportunities.append(self._build(bucket[0], 'competitor_saturation', title, score, ('dense competitor footprint observed',)))
        return tuple(opportunities)

    def _build(self, signal: UnifiedSignal, opportunity_type: str, title: str, score, rationale: tuple[str, ...]) -> OpportunityEvidence:
        return OpportunityEvidence(
            tenant_id=signal.tenant_id,
            opportunity_type=opportunity_type,
            entity_id=signal.entity_id,
            title=title,
            confidence=min(score.structured_importance, 1.0),
            support_signals=int(score.signals_count),
            rationale=rationale,
            payload={'entity_kind': signal.entity_kind, 'source_family': signal.source_family, 'provider': signal.provider},
        )


__all__ = ['CANON_MARKET_INTELLIGENCE_OPPORTUNITY_DETECTOR', 'OpportunityDetector']
