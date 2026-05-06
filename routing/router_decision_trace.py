from __future__ import annotations

class RouterDecisionTrace:
    def build(self, *, ranked_candidates: tuple[object, ...]) -> dict[str, object]:
        return {
            "ranked_business_ids": [c.business_id for c in ranked_candidates],
            "scores": {c.business_id: float(c.rank_score) for c in ranked_candidates},
            "blocked_business_ids": [c.business_id for c in ranked_candidates if c.blocked],
        }
