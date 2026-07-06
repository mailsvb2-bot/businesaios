from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from core.pricing.rl.guard import PricingSelectionContext
from core.pricing.rl.scoring import score_candidates
from core.scorers.pricing import choose_candidate as select_candidate

Json = dict[str, Any]


class PricingSelectionService:
    """Pure selection helper.

    Important:
      - computes candidate ranking
      - returns selected proposal
      - does NOT emit actions
      - does NOT mutate policy
    """

    def choose_candidate(
        self,
        *,
        ctx: PricingSelectionContext,
        candidates: Iterable[Json],
        evidence: Json,
    ) -> Json:
        ctx.validate()
        cand_list: list[Json] = list(candidates)
        scored = score_candidates(cand_list, evidence=evidence)
        chosen = select_candidate(scored)
        return {
            "tenant_id": ctx.tenant_id,
            "decision_id": ctx.decision_id,
            "correlation_id": ctx.correlation_id,
            "selected": chosen,
            "scored_count": len(scored),
        }

    select = choose_candidate
