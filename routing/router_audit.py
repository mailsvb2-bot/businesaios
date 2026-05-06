from __future__ import annotations

class RouterAudit:
    def record(self, *, request_id: str, ranked_candidates: tuple[object, ...]) -> dict[str, object]:
        return {"request_id": request_id, "ranked": [c.business_id for c in ranked_candidates]}
