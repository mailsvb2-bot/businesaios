from __future__ import annotations

from typing import Protocol


class DecisionRunPort(Protocol):
    def run(self, candidates: list[object], constraints: dict | None = None) -> tuple[object, object]: ...


class OpportunityToDecisionFlow:
    def run(
        self,
        candidates: list[object],
        decision_pipeline: DecisionRunPort,
        constraints: dict | None = None,
    ) -> tuple[object, object]:
        return decision_pipeline.run(candidates, constraints)
