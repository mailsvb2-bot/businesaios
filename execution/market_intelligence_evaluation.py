from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CANON_MARKET_INTELLIGENCE_EVALUATION = True


@dataclass(frozen=True)
class GoldenRecord:
    entity_title: str
    provider: str
    expected_external_id: str
    expected_kind: str


@dataclass
class MarketIntelligenceEvaluationFramework:
    def provider_quality_score(self, *, records: list[Mapping[str, Any]]) -> float:
        if not records:
            return 0.0
        with_identity = sum(1 for row in records if str(row.get('external_id') or '').strip())
        with_title = sum(1 for row in records if str(row.get('title') or '').strip())
        with_url = sum(1 for row in records if str(row.get('url') or '').strip())
        return round((with_identity + with_title + with_url) / (3.0 * len(records)), 4)

    def fusion_precision_proxy(self, *, fused_entities: list[Mapping[str, Any]]) -> float:
        if not fused_entities:
            return 0.0
        confident = 0
        for item in fused_entities:
            confidence = float(item.get('confidence') or item.get('identity', {}).get('confidence') or 0.0)
            reason = str(item.get('reason') or item.get('identity', {}).get('reason') or '')
            if confidence >= 0.82 and 'anti_overmerge' not in reason:
                confident += 1
        return round(confident / len(fused_entities), 4)

    def trend_accuracy_proxy(self, *, predicted: list[Mapping[str, Any]], observed: list[Mapping[str, Any]]) -> float:
        if not predicted or not observed:
            return 0.0
        predicted_titles = {str(row.get('entity_title') or '').strip().lower() for row in predicted}
        observed_titles = {str(row.get('entity_title') or '').strip().lower() for row in observed}
        if not predicted_titles and not observed_titles:
            return 1.0
        intersection = len(predicted_titles & observed_titles)
        union = len(predicted_titles | observed_titles)
        return round(intersection / max(1, union), 4)

    def detector_recall_proxy(self, *, opportunities: list[Mapping[str, Any]], golden: list[GoldenRecord]) -> float:
        if not golden:
            return 0.0
        titles = {str(item.get('title') or item.get('entity_title') or '').strip().lower() for item in opportunities}
        hits = sum(1 for row in golden if row.entity_title.strip().lower() in titles)
        return round(hits / len(golden), 4)

    def regression_summary(self, *, provider_records: list[Mapping[str, Any]], fused_entities: list[Mapping[str, Any]], golden: list[GoldenRecord]) -> dict[str, Any]:
        return {'provider_quality_score': self.provider_quality_score(records=provider_records), 'fusion_precision_proxy': self.fusion_precision_proxy(fused_entities=fused_entities), 'detector_recall_proxy': self.detector_recall_proxy(opportunities=fused_entities, golden=golden)}
