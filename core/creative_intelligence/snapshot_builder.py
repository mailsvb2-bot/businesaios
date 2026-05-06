from __future__ import annotations

from core.creative_intelligence.downside_envelope import downside_envelope
from core.explainability.creative_reason_builder import build_creative_reasons
from core.explainability.explanation_lines import to_lines
from core.creative_intelligence.expected_value_score import expected_value_score
from core.creative_intelligence.experiment_confidence_builder import build_experiment_confidence_snapshot
from core.creative_intelligence.incrementality_builder import build_incrementality_snapshot
from core.creative_intelligence.models import (
    CreativeEconomicsInput,
    CreativeEvidenceBundle,
    CreativeIntelligenceSnapshot,
)
from core.creative_intelligence.pnl_builder import build_pnl_snapshot
from core.scorers.portfolio import portfolio_rank_score


def build_creative_snapshot(
    *,
    item: CreativeEconomicsInput,
    evidence: CreativeEvidenceBundle,
) -> CreativeIntelligenceSnapshot:
    pnl = build_pnl_snapshot(item)
    incrementality = build_incrementality_snapshot(
        creative_id=item.creative_id,
        result=evidence.causal_result,
    )
    experiment_confidence = build_experiment_confidence_snapshot(
        creative_id=item.creative_id,
        summary=evidence.experiment_summary,
    )
    ev = expected_value_score(
        item=item,
        pnl=pnl,
        incrementality=incrementality,
        confidence=experiment_confidence,
    )
    downside = downside_envelope(
        pnl=pnl,
        incrementality=incrementality,
        confidence=experiment_confidence,
    )
    draft = CreativeIntelligenceSnapshot(
        creative_id=item.creative_id,
        pnl=pnl,
        incrementality=incrementality,
        experiment_confidence=experiment_confidence,
        expected_value_score=ev,
        downside_envelope=downside,
        portfolio_rank_score=0.0,
        explanations=(),
    )
    return CreativeIntelligenceSnapshot(
        creative_id=draft.creative_id,
        pnl=draft.pnl,
        incrementality=draft.incrementality,
        experiment_confidence=draft.experiment_confidence,
        expected_value_score=draft.expected_value_score,
        downside_envelope=draft.downside_envelope,
        portfolio_rank_score=portfolio_rank_score(draft),
        explanations=to_lines(build_creative_reasons(draft)),
    )
