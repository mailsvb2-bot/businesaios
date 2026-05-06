from __future__ import annotations


class FeedbackToStrategyFlow:
    def run(self, feedback: dict) -> dict:
        return {'strategy_feedback': dict(feedback)}
