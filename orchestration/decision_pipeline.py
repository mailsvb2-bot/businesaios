from __future__ import annotations
from core.constraints.decision import DecisionConstraints
from kernel.decision_request import DecisionRequest
from kernel.decision_space import DecisionSpace


class DecisionPipeline:
    def __init__(self, decision_core: object) -> None:
        self._decision_core = decision_core

    def run(self, candidates: list[object], constraints: dict | None = None, request: DecisionRequest | None = None) -> tuple[object, object]:
        normalized_constraints = DecisionConstraints(**(constraints or {}))
        normalized_request = request or DecisionRequest(
            business_id='unknown_business',
            objective=normalized_constraints.objective_name,
            input_bundle_id='bundle_from_decision_pipeline',
        )
        space = DecisionSpace(candidates=candidates)
        return self._decision_core.issue(space, normalized_constraints, normalized_request)
