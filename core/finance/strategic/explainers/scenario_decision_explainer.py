from __future__ import annotations

from core.finance.strategic.types import Scenario


class ScenarioDecisionExplainer:
    def explain(self, scenario: Scenario, *, score: object | None = None, rationale: tuple[str, ...] = ()) -> str:
        suffix = f" score={score}" if score is not None else ""
        reasons = f" Reasons: {'; '.join(rationale)}." if rationale else ""
        return (
            f"Selected {scenario.name} with probability {scenario.probability}, "
            f"revenue multiplier {scenario.revenue_multiplier}, cost multiplier {scenario.cost_multiplier}.{suffix}"
            f"{reasons}"
        )
