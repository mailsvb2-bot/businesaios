from __future__ import annotations

import math

from config.demand_scoring import MATCH_ADJUSTMENTS
from matching.scorers import (
    CapacityFitScore,
    ConversionProbabilityScore,
    CustomerSatisfactionProbabilityScore,
    FairDistributionScore,
    GeoFitScore,
    IntentFitScore,
    PriceFitScore,
    RepeatPurchaseProbabilityScore,
    ReputationFitScore,
    ResponseFitScore,
    RevenuePotentialScore,
    RiskPenaltyScore,
)
from registry.match_scorer_registry import MatchScorerRegistry


def rank_candidates_desc(
    candidates: tuple[object, ...],
    *,
    score_attr: str,
    blocked_attr: str = "blocked",
) -> tuple[object, ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                float(getattr(candidate, score_attr, 0.0)),
                -int(bool(getattr(candidate, blocked_attr, False))),
            ),
            reverse=True,
        )
    )


class MatchRanker:
    def rank(self, candidates: tuple[object, ...]) -> tuple[object, ...]:
        return rank_candidates_desc(candidates, score_attr="score")


class MatchRanking:
    def __init__(self, *, scorers: MatchScorerRegistry | None = None) -> None:
        self._scorers = scorers or MatchScorerRegistry()
        if not self._scorers.snapshot():
            self._register_default_scorers()
        self._ranker = MatchRanker()

    def _register_default_scorers(self) -> None:
        for scorer in (
            IntentFitScore(),
            GeoFitScore(),
            PriceFitScore(),
            CapacityFitScore(),
            ResponseFitScore(),
            ReputationFitScore(),
            ConversionProbabilityScore(),
            RevenuePotentialScore(),
            CustomerSatisfactionProbabilityScore(),
            RepeatPurchaseProbabilityScore(),
            RiskPenaltyScore(),
            FairDistributionScore(),
        ):
            self._scorers.register(getattr(scorer, 'NAME', scorer.__class__.__name__), scorer)

    def rank(self, candidates: tuple[object, ...]) -> tuple[object, ...]:
        return self._ranker.rank(candidates)

    def score_breakdown(self, *, intent, profile, live_state, gravity_snapshot=None) -> dict[str, float]:
        breakdown: dict[str, float] = {}
        for name, scorer in self._scorers.items():
            breakdown[str(name)] = self.finite(
                scorer.score(intent=intent, profile=profile, live_state=live_state)
            )
        if gravity_snapshot is not None:
            vectors = dict(gravity_snapshot.get('vectors') or {})
            vector = vectors.get(profile.business_id)
            if vector is not None:
                breakdown['demand_gravity_score'] = self.finite(
                    getattr(vector, 'attraction', 0.0) or 0.0
                )
                breakdown['demand_pressure'] = self.finite(
                    getattr(vector, 'demand_pressure', 0.0) or 0.0
                ) * MATCH_ADJUSTMENTS.demand_pressure_weight
                breakdown['supply_pressure_penalty'] = -self.finite(
                    getattr(vector, 'supply_pressure', 0.0) or 0.0
                ) * MATCH_ADJUSTMENTS.supply_pressure_penalty_weight
                breakdown['geo_distance_penalty'] = -self.finite(
                    getattr(vector, 'geo_distance_penalty', 0.0) or 0.0
                )
            policy_state = gravity_snapshot.get('policy_state')
            if policy_state is not None:
                breakdown['policy_adjustment'] = self._policy_adjustment(
                    policy_state,
                    profile.business_id,
                )
        return breakdown

    def _policy_adjustment(self, policy_state, business_id: str) -> float:
        adjust = getattr(policy_state, 'adjustment_for', None)
        if not callable(adjust):
            return 0.0
        raw = self.finite(adjust(business_id))
        return max(
            -MATCH_ADJUSTMENTS.max_policy_adjustment_abs,
            min(MATCH_ADJUSTMENTS.max_policy_adjustment_abs, raw),
        )

    def finite(self, value: object) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(numeric):
            return 0.0
        return numeric
