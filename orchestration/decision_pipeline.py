from __future__ import annotations

from core.constraints.decision import DecisionConstraints
from kernel.decision_request import DecisionRequest
from kernel.decision_space import DecisionSpace

CANON_DECISION_PIPELINE_RECOMMENDATION_ONLY = True
CANON_DECISION_PIPELINE_NO_SOVEREIGN_ISSUANCE = True


class DecisionPipeline:
    """Compatibility facade for non-sovereign recommendation selection.

    The historical constructor argument remains named ``decision_core`` for API
    compatibility, but the object must explicitly identify itself as the
    recommendation-only ``DecisionService`` and expose ``select_action``. Final
    signed decisions are issued only by ``core.ai.DecisionCore``.
    """

    def __init__(self, decision_core: object) -> None:
        if not bool(getattr(decision_core, "IS_NON_SOVEREIGN", False)):
            raise TypeError(
                "DecisionPipeline requires a non-sovereign selection service"
            )
        if not bool(getattr(decision_core, "OWNS_ONLY_SELECTION", False)):
            raise TypeError(
                "DecisionPipeline selection service must own selection only"
            )
        select_action = getattr(decision_core, "select_action", None)
        if not callable(select_action):
            raise TypeError(
                "DecisionPipeline selection service requires select_action"
            )
        self._selection_service = decision_core

    def run(
        self,
        candidates: list[object],
        constraints: dict | None = None,
        request: DecisionRequest | None = None,
    ) -> tuple[object, object]:
        normalized_constraints = DecisionConstraints(**(constraints or {}))
        normalized_request = request or DecisionRequest(
            business_id="unknown_business",
            objective=normalized_constraints.objective_name,
            input_bundle_id="bundle_from_decision_pipeline",
        )
        space = DecisionSpace(candidates=candidates)
        return self._selection_service.select_action(
            space,
            normalized_constraints,
            normalized_request,
        )
