from __future__ import annotations

from contracts.matching.routing_candidate import RoutingCandidate
from matching.ranking import rank_candidates_desc
from shared.numbers import coerce_float


class RoutingCandidateBuilder:
    def build(
        self,
        *,
        candidate: object,
        policy_tags: tuple[str, ...],
        adjusted_score: object,
        blocked: bool,
    ) -> RoutingCandidate:
        match_score = coerce_float(getattr(candidate, 'score', 0.0), 0.0)
        adjusted = coerce_float(adjusted_score, match_score)
        tags = tuple(dict.fromkeys(str(tag) for tag in policy_tags if str(tag).strip()))
        return RoutingCandidate(
            business_id=candidate.business_id,
            rank_score=adjusted,
            policy_tags=tags,
            trace={'match_score': match_score, 'adjusted_score': adjusted},
            blocked=bool(blocked or getattr(candidate, 'blocked', False)),
        )


class RoutingCandidateRanker:
    def rank(self, candidates: tuple[RoutingCandidate, ...]) -> tuple[RoutingCandidate, ...]:
        return rank_candidates_desc(candidates, score_attr='rank_score')


__all__ = ['RoutingCandidateBuilder', 'RoutingCandidateRanker']
