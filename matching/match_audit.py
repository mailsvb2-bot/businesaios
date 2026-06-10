from __future__ import annotations


class MatchAudit:
    def record(self, *, request_id: str, candidates: tuple[object, ...]) -> dict[str, object]:
        return {"request_id": str(request_id), "candidate_count": len(candidates), "blocked_count": sum(1 for c in candidates if c.blocked)}
