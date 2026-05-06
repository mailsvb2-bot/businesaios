from __future__ import annotations

from dataclasses import dataclass

from execution.goal_score import GoalScore, GoalScoreEngine


CANON_HEADLESS_SCENARIO_GOAL_SCORE = True


@dataclass(frozen=True)
class ScenarioGoalScoreEngine:
    """
    Thin scenario-aware scoring layer.

    Hard rule:
    - must not infer semantics from free-text goal text
    - may only add bounded bonuses from explicit observed scenario fields
    """

    base: GoalScoreEngine

    def score(self, *, scenario: str | None, goal: str, feedback: dict, step_ok: bool) -> GoalScore:
        del goal
        base_score = self.base.score(goal="", feedback=feedback, step_ok=step_ok)
        value = float(base_score.value)
        reasons = list(base_score.reasons)

        scenario_name = str(scenario or "").strip().lower()

        if scenario_name == "acquire_client" and bool(feedback.get("converted")):
            value += 0.05
            reasons.append("scenario_acquire_client_bonus")
        elif scenario_name == "pricing_adjustment" and float(feedback.get("revenue") or 0.0) > 0:
            value += 0.05
            reasons.append("scenario_pricing_bonus")
        elif scenario_name == "lead_processing" and bool(feedback.get("responded")):
            value += 0.05
            reasons.append("scenario_lead_processing_bonus")
        elif scenario_name == "mini_funnel_launch" and bool(feedback.get("funnel_started")):
            value += 0.05
            reasons.append("scenario_mini_funnel_bonus")
        elif scenario_name == "retention_recovery" and bool(feedback.get("customer_success")):
            value += 0.05
            reasons.append("scenario_retention_bonus")

        return GoalScore(
            value=max(0.0, min(1.0, float(value))),
            reasons=tuple(reasons),
        )


__all__ = [
    "CANON_HEADLESS_SCENARIO_GOAL_SCORE",
    "ScenarioGoalScoreEngine",
]
