from __future__ import annotations


class ComplaintPenaltyEngine:
    def penalty(self, outcome: dict[str, object]) -> float:
        return 0.4 if outcome.get("complaint") else 0.0
