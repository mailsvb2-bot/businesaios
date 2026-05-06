from __future__ import annotations

from dataclasses import dataclass

from runtime.creative import (
    CreativeEconomicsInput,
    CreativeEvidenceBundle,
    CreativeIntelligenceSnapshot,
    build_creative_recommendations,
    build_creative_snapshot,
    rank_portfolio,
    replace_market_fit_score,
)
from runtime.decisioning import RecommendationSet
from runtime.market.market_snapshot import MarketSnapshot
from runtime.runtime_observability import RuntimeObservability


@dataclass
class CreativeIntelligenceService:
    observability: RuntimeObservability

    def inspect_many(
        self,
        *,
        items: tuple[CreativeEconomicsInput, ...],
        evidence_map: dict[str, CreativeEvidenceBundle],
        market_snapshot: MarketSnapshot,
    ) -> tuple[CreativeIntelligenceSnapshot, ...]:
        snapshots: list[CreativeIntelligenceSnapshot] = []
        segment_market = {
            item.segment_key: item
            for item in market_snapshot.segment_states
        }
        for item in items:
            evidence = evidence_map.get(item.creative_id, CreativeEvidenceBundle())
            adjusted = item
            segment_state = segment_market.get(item.segment_key)
            if segment_state is not None:
                adjusted = replace_market_fit_score(
                    item,
                    max(0.0, min(1.0, 0.60 * segment_state.micro_score + 0.40 * segment_state.persistence_score)),
                )
            snapshot = build_creative_snapshot(item=adjusted, evidence=evidence)
            snapshots.append(snapshot)
            self.observability.record_model_snapshot(
                model_name="creative_intelligence",
                metric_name=f"expected_value:{snapshot.creative_id}",
                metric_value=snapshot.expected_value_score,
            )
        return rank_portfolio(tuple(snapshots))

    def recommendations(
        self,
        *,
        snapshots: tuple[CreativeIntelligenceSnapshot, ...],
        total_budget: float,
    ) -> RecommendationSet:
        return build_creative_recommendations(
            snapshots=snapshots,
            total_budget=total_budget,
        )
