from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

Json = Dict[str, Any]


@dataclass(frozen=True)
class BudgetAllocation:
    per_campaign_minor: Dict[str, int]
    notes: str = ""


class BudgetAllocator:
    """Deterministic allocator.

    Strategy:
    - if campaigns have 'score' -> proportional allocation
    - else equal split
    """

    def allocate(self, *, total_budget_minor: int, campaigns: List[Json]) -> BudgetAllocation:
        total = max(int(total_budget_minor or 0), 0)
        if total <= 0 or not campaigns:
            return BudgetAllocation({}, notes="no_budget_or_campaigns")

        ids = [str(c.get("id") or c.get("campaign_id") or "") for c in campaigns]
        ids = [i for i in ids if i]
        if not ids:
            return BudgetAllocation({}, notes="no_campaign_ids")

        scores = []
        for c in campaigns:
            s = c.get("score")
            try:
                scores.append(float(s))
            except Exception:
                scores.append(0.0)

        if any(s > 0 for s in scores):
            ssum = sum(max(s, 0.0) for s in scores) or 1.0
            alloc = {ids[i]: int(total * (max(scores[i], 0.0) / ssum)) for i in range(len(ids))}
        else:
            per = total // len(ids)
            alloc = {cid: per for cid in ids}

        # fix rounding: ensure sum <= total
        used = sum(alloc.values())
        if used > total:
            scale = total / max(used, 1)
            alloc = {k: int(v * scale) for k, v in alloc.items()}

        return BudgetAllocation(alloc, notes="ok")
