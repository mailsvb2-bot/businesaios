from __future__ import annotations

from config.routing_limits import ROUTING_SCORE_FLOOR
from shared.numbers import coerce_float


class DemandDecisionCandidateBuilder:
    def build(self, routing_preparation: dict[str, object]) -> tuple[object, ...]:
        ranked = tuple(routing_preparation.get('ranked_candidates') or ())
        return tuple(
            candidate
            for candidate in ranked
            if coerce_float(getattr(candidate, 'rank_score', 0.0), 0.0) >= ROUTING_SCORE_FLOOR
        )
