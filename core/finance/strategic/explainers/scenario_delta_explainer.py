from __future__ import annotations


class ScenarioDeltaExplainer:
    def explain(self, comparison: dict) -> str:
        return f"Revenue delta={comparison['revenue_delta']}, cost delta={comparison['cost_delta']}, probability delta={comparison['probability_delta']}"
