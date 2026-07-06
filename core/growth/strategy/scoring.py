"""Deterministic scoring for growth hypotheses (ICE-ish + risk penalty)."""

from __future__ import annotations

from collections.abc import Iterable

from config.scoring_behavior_policy import (
    DEFAULT_GROWTH_STRATEGY_SCORING_POLICY,
    GrowthStrategyScoringPolicy,
)

from .contracts import GrowthHypothesisV1, OpportunityScoreV1


def score_hypothesis(
    h: GrowthHypothesisV1,
    *,
    policy: GrowthStrategyScoringPolicy = DEFAULT_GROWTH_STRATEGY_SCORING_POLICY,
) -> OpportunityScoreV1:
    impact = _impact_heuristic(h, policy=policy)
    confidence = _confidence_heuristic(h, policy=policy)
    ease = float(policy.effort_ease_by_level.get(h.effort, policy.default_ease))
    risk_penalty = float(policy.risk_penalty_by_level.get(h.risk, policy.default_risk_penalty))

    raw = max(0.0, (impact * confidence * ease) - risk_penalty)
    score = float(round(min(1.0, raw) * 100.0, 2))

    rationale: list[str] = []
    rationale.append(f"impact={impact:.2f}")
    rationale.append(f"confidence={confidence:.2f}")
    rationale.append(f"ease={ease:.2f} (effort={h.effort})")
    rationale.append(f"risk_penalty={risk_penalty:.2f} (risk={h.risk})")

    return OpportunityScoreV1(
        hypothesis_id=h.hypothesis_id,
        score=score,
        impact=float(round(impact, 3)),
        confidence=float(round(confidence, 3)),
        ease=float(round(ease, 3)),
        risk_penalty=float(round(risk_penalty, 3)),
        rationale=tuple(rationale),
    )


def rank_hypotheses(
    hypotheses: Iterable[GrowthHypothesisV1],
    *,
    policy: GrowthStrategyScoringPolicy = DEFAULT_GROWTH_STRATEGY_SCORING_POLICY,
) -> tuple[OpportunityScoreV1, ...]:
    scored = [score_hypothesis(h, policy=policy) for h in hypotheses]
    scored.sort(key=lambda s: (s.score, s.impact, s.confidence, s.ease), reverse=True)
    return tuple(scored)


def _impact_heuristic(h: GrowthHypothesisV1, *, policy: GrowthStrategyScoringPolicy) -> float:
    txt = (h.expected_impact or "").lower()
    for signal, mapped_score in policy.impact_by_signal.items():
        if signal in txt:
            return float(mapped_score)
    if h.stage in policy.stage_impact_by_stage:
        return float(policy.stage_impact_by_stage[h.stage])
    return float(policy.default_impact)


def _confidence_heuristic(h: GrowthHypothesisV1, *, policy: GrowthStrategyScoringPolicy) -> float:
    mech = (h.mechanism or "").lower()
    hints = 0
    if len(mech) >= int(policy.mechanism_length_threshold):
        hints += 1
    if any(w in mech for w in policy.evidence_keywords):
        hints += 1
    if any(w in mech for w in policy.experiment_keywords):
        hints += 1
    normalized_hints = min(3, max(0, int(hints)))
    return float(policy.confidence_by_hint_count.get(normalized_hints, policy.confidence_by_hint_count[0]))
