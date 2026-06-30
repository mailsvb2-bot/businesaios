from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Iterable, Mapping

from contracts.platforms.market_intelligence_advanced_contract import UnifiedSignal
from execution.market_intelligence_advanced_memory_bridge import AdvancedBusinessMemoryBridge
from execution.market_intelligence_advanced_models import TrendPoint
from execution.market_intelligence_advanced_world_state_bridge import AdvancedWorldStateBridge
from execution.market_intelligence_data_quality import DataQualityGuard
from execution.market_intelligence_human_feedback import HumanFeedbackLoop
from execution.market_intelligence_incremental_sync import IncrementalSyncEngine
from execution.market_intelligence_knowledge_graph import KnowledgeGraphLayer
from execution.market_intelligence_opportunity_detector import OpportunityDetector
from execution.market_intelligence_pattern_extractor import ContentOfferPatternExtractor
from execution.market_intelligence_sampling import AdaptiveSamplingStrategy, SamplingCandidate
from execution.market_intelligence_scoring import EvidenceScoringEngine
from execution.market_intelligence_tenant_isolation import TenantIntelligenceScope, TenantIsolationGuard
from execution.market_intelligence_trend_engine import TemporalTrendEngine


CANON_MARKET_INTELLIGENCE_ADVANCED_PIPELINE = True


_SOURCE_FAMILY_SIGNAL_KIND = {
    'marketplace': 'demand',
    'ads_library': 'competitor',
    'competitor_analytics': 'competitor',
    'search_intelligence': 'demand',
    'professional_network': 'complaint',
    'content_platform': 'content',
    'app_store': 'complaint',
    'review_platform': 'complaint',
    'landing_intelligence': 'pricing',
    'video_platform': 'content',
    'ads_spy': 'competitor',
    'newsletter_intelligence': 'content',
}


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


@dataclass
class MarketIntelligenceAdvancedPipeline:
    quality_guard: DataQualityGuard = field(default_factory=DataQualityGuard)
    incremental_sync: IncrementalSyncEngine = field(default_factory=IncrementalSyncEngine)
    scorer: EvidenceScoringEngine = field(default_factory=EvidenceScoringEngine)
    opportunity_detector: OpportunityDetector = field(default_factory=OpportunityDetector)
    trend_engine: TemporalTrendEngine = field(default_factory=TemporalTrendEngine)
    pattern_extractor: ContentOfferPatternExtractor = field(default_factory=ContentOfferPatternExtractor)
    graph_layer: KnowledgeGraphLayer = field(default_factory=KnowledgeGraphLayer)
    sampling_strategy: AdaptiveSamplingStrategy = field(default_factory=AdaptiveSamplingStrategy)
    feedback_loop: HumanFeedbackLoop = field(default_factory=HumanFeedbackLoop)
    tenant_guard: TenantIsolationGuard = field(default_factory=TenantIsolationGuard)
    world_state_bridge: AdvancedWorldStateBridge = field(default_factory=AdvancedWorldStateBridge)
    memory_bridge: AdvancedBusinessMemoryBridge = field(default_factory=AdvancedBusinessMemoryBridge)

    def process_records(
        self,
        *,
        tenant_id: str,
        provider: str,
        source_family: str,
        scope_key: str,
        records: Iterable[Mapping[str, Any]],
        tenant_scope: TenantIntelligenceScope | None = None,
        entity_kind: str = 'unknown',
        signal_kind: str | None = None,
    ) -> dict[str, Any]:
        payload = {'tenant_id': tenant_id, 'provider': provider, 'source_family': source_family, 'limit': len(tuple(records)) if not isinstance(records, (list, tuple)) else len(records)}
        if tenant_scope is not None:
            payload = self.tenant_guard.enforce(payload, tenant_scope)
        source_rows = tuple(dict(item) for item in records if isinstance(item, Mapping))
        cleaned_rows, quality_report = self.quality_guard.process(source_rows)
        diff = self.incremental_sync.diff(
            tenant_id=tenant_id,
            provider=provider,
            source_family=source_family,
            scope_key=scope_key,
            records=cleaned_rows,
        )
        normalized_signal_kind = _safe_text(signal_kind, default=_SOURCE_FAMILY_SIGNAL_KIND.get(source_family, 'generic'))
        signals = self._build_signals(
            tenant_id=tenant_id,
            provider=provider,
            source_family=source_family,
            entity_kind=entity_kind,
            signal_kind=normalized_signal_kind,
            rows=diff.new_records + diff.changed_records,
        )
        scores = self.scorer.score(signals)
        opportunities = self.opportunity_detector.detect(signals)
        for score in scores:
            self.trend_engine.observe(
                TrendPoint(
                    tenant_id=tenant_id,
                    entity_id=score.entity_id,
                    metric='structured_importance',
                    value=float(score.structured_importance),
                    metadata={'provider': provider, 'source_family': source_family},
                )
            )
        trend_summaries = [
            self.trend_engine.summarize(tenant_id=tenant_id, entity_id=score.entity_id, metric='structured_importance').as_dict()
            for score in scores[:25]
        ]
        patterns = self.pattern_extractor.extract(cleaned_rows).as_dict()
        knowledge_edges = [edge.as_dict() for edge in self.graph_layer.build_edges(cleaned_rows)]
        world_state_patch = self.world_state_bridge.build_patch(signals=signals, opportunities=opportunities, trend_summaries=trend_summaries)
        memory_payload = self.memory_bridge.to_memory_payload(signals=signals, opportunities=opportunities, pattern_payload=patterns)
        return {
            'tenant_id': tenant_id,
            'provider': provider,
            'source_family': source_family,
            'scope_key': scope_key,
            'quality_report': quality_report.as_dict(),
            'cursor': diff.cursor.as_dict(),
            'new_records': [dict(item) for item in diff.new_records],
            'changed_records': [dict(item) for item in diff.changed_records],
            'unchanged_records_count': len(diff.unchanged_records),
            'signals': [item.as_dict() for item in signals],
            'scores': [item.as_dict() for item in scores],
            'opportunities': [item.as_dict() for item in opportunities],
            'trend_summaries': trend_summaries,
            'patterns': patterns,
            'knowledge_edges': knowledge_edges,
            'world_state_patch': world_state_patch,
            'memory_payload': memory_payload,
            'tenant_payload': payload,
        }

    def select_sampling_plan(self, *, candidates: Iterable[Mapping[str, Any]], limit: int = 5) -> tuple[SamplingCandidate, ...]:
        normalized = [
            SamplingCandidate(
                provider=_safe_text(item.get('provider')),
                source_family=_safe_text(item.get('source_family')),
                priority=float(item.get('priority') or 0.5),
                exploration_bias=float(item.get('exploration_bias') or 0.1),
                metadata=_safe_dict(item.get('metadata')),
            )
            for item in candidates
            if isinstance(item, Mapping)
        ]
        return self.sampling_strategy.select(normalized, limit=limit)

    def feedback_summary(self, *, tenant_id: str, entity_id: str) -> dict[str, Any]:
        return self.feedback_loop.summarize(tenant_id=tenant_id, entity_id=entity_id)

    def _build_signals(
        self,
        *,
        tenant_id: str,
        provider: str,
        source_family: str,
        entity_kind: str,
        signal_kind: str,
        rows: Iterable[Mapping[str, Any]],
    ) -> tuple[UnifiedSignal, ...]:
        signals: list[UnifiedSignal] = []
        for row in rows:
            payload = dict(row)
            entity_id = _safe_text(payload.get('entity_id') or payload.get('product_id') or payload.get('external_id') or payload.get('record_id') or payload.get('id') or payload.get('url') or payload.get('title'))
            if not entity_id:
                continue
            observed_at = _safe_text(payload.get('updated_at') or payload.get('published_at') or payload.get('observed_at'))
            signals.append(
                UnifiedSignal(
                    tenant_id=tenant_id,
                    entity_id=entity_id,
                    entity_kind=_safe_text(payload.get('entity_kind'), default=entity_kind),
                    source_family=source_family,
                    provider=provider,
                    signal_kind=_safe_text(payload.get('signal_kind'), default=signal_kind),
                    observed_at=observed_at,
                    confidence=self._score_confidence(payload),
                    strength=self._score_strength(payload),
                    freshness=0.0,
                    frequency=self._score_frequency(payload),
                    tags=tuple(str(item).strip() for item in payload.get('tags', ()) if str(item).strip()) if isinstance(payload.get('tags'), (list, tuple, set)) else (),
                    payload=payload,
                )
            )
        return tuple(signals)

    def _score_confidence(self, row: Mapping[str, Any]) -> float:
        score = 0.2
        for key in ('title', 'url', 'external_id', 'record_id'):
            if _safe_text(row.get(key)):
                score += 0.15
        if row.get('rating') is not None:
            score += 0.1
        if row.get('review_count') is not None:
            score += 0.1
        return max(0.0, min(score, 1.0))

    def _score_strength(self, row: Mapping[str, Any]) -> float:
        raw = row.get('engagement', row.get('impressions', row.get('review_count', row.get('frequency', 0))))
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        if value <= 0:
            return 0.2
        if value >= 100000:
            return 1.0
        if value >= 10000:
            return 0.8
        if value >= 1000:
            return 0.6
        if value >= 100:
            return 0.4
        return 0.25

    def _score_frequency(self, row: Mapping[str, Any]) -> float:
        if row.get('review_count') is not None:
            try:
                count = max(0.0, float(row.get('review_count')))
            except (TypeError, ValueError):
                count = 0.0
            return max(0.0, min(count / 100.0, 1.0))
        return 0.2


__all__ = ['CANON_MARKET_INTELLIGENCE_ADVANCED_PIPELINE', 'MarketIntelligenceAdvancedPipeline']
