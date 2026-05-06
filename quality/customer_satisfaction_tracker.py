from __future__ import annotations

class CustomerSatisfactionTracker:
    def score(self, outcome: dict[str, object]) -> float:
        return 1.0 if outcome.get("converted") else 0.5 if outcome.get("responded") else 0.1
