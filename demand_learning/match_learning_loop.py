from __future__ import annotations

class MatchLearningLoop:
    def propose_weight_updates(self, feedback_rows: tuple[dict[str, object], ...]) -> dict[str, float]:
        converted = sum(1 for row in feedback_rows if row.get("converted"))
        total = max(1, len(feedback_rows))
        return {"conversion_signal": converted / total}
