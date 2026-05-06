from __future__ import annotations

from contracts.matching.match_bundle import MatchBundle
from contracts.matching.match_candidate import MatchCandidate
from shared.numbers import coerce_float


class MatchScoreAggregator:
    def aggregate(self, breakdown: dict[str, float]) -> float:
        if not breakdown:
            return 0.0
        return float(sum(float(value) for value in breakdown.values()) / len(breakdown))


class MatchExplainer:
    def explain(self, breakdown: dict[str, float]) -> tuple[str, ...]:
        return tuple(f"{name}={value:.3f}" for name, value in sorted(breakdown.items()))


class MatchCandidateBuilder:
    def __init__(
        self,
        *,
        score_aggregator: MatchScoreAggregator | None = None,
        explainer: MatchExplainer | None = None,
    ) -> None:
        self._score_aggregator = score_aggregator or MatchScoreAggregator()
        self._explainer = explainer or MatchExplainer()

    def build(
        self,
        business_id: str,
        breakdown: dict[str, float],
        reasons: tuple[str, ...] | None = None,
        blocked: bool = False,
    ) -> MatchCandidate:
        normalized_business_id = str(business_id or '').strip()
        if not normalized_business_id:
            raise ValueError('match candidate requires business_id')
        normalized_breakdown = {
            str(name): coerce_float(value, 0.0)
            for name, value in dict(breakdown or {}).items()
        }
        resolved_reasons = reasons if reasons is not None else self._explainer.explain(normalized_breakdown)
        normalized_reasons = tuple(
            dict.fromkeys(str(item) for item in resolved_reasons if str(item).strip())
        )
        score = self._score_aggregator.aggregate(normalized_breakdown)
        return MatchCandidate(
            business_id=normalized_business_id,
            score=0.0 if blocked else float(round(score, 6)),
            score_breakdown=normalized_breakdown,
            reasons=normalized_reasons,
            blocked=bool(blocked),
        )


class MatchBundleBuilder:
    def build(
        self,
        request_id: str,
        candidates: tuple[object, ...],
        audit: dict[str, object],
    ) -> MatchBundle:
        return MatchBundle(
            request_id=str(request_id),
            candidates=candidates,
            audit=dict(audit),
        )
