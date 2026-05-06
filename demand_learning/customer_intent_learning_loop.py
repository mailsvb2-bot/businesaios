from __future__ import annotations

class CustomerIntentLearningLoop:
    def propose_intent_updates(self, feedback_rows: tuple[dict[str, object], ...]) -> dict[str, float]:
        return {"rows_seen": float(len(feedback_rows))}
