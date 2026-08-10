from __future__ import annotations


class NoResponsePenaltyEngine:
    def penalty(self, outcome: dict[str, object]) -> float:
        return 0.5 if not outcome.get("responded", False) else 0.0
