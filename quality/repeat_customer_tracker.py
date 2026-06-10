from __future__ import annotations


class RepeatCustomerTracker:
    def bonus(self, outcome: dict[str, object]) -> float:
        return 0.2 if outcome.get("repeat_customer") else 0.0
