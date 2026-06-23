from __future__ import annotations

from core.ai import get_decision_core_singleton
from core.strategic_horizon.engine import CANONICAL_DECISION_OPTIMIZE_METHOD


def process_demand(input: object) -> object:
    """Single canonical demand execution contract.

    Marketplace demand must enter the system through the one canonical
    DecisionCore optimize() surface. No fallback to run()/decide() is
    allowed, otherwise the entrypoint becomes ambiguous and the single
    execution contract regresses.
    """
    decision_core = get_decision_core_singleton()
    optimize = getattr(decision_core, CANONICAL_DECISION_OPTIMIZE_METHOD, None)
    if not callable(optimize):
        raise TypeError("canonical_decision_core_optimize_required")
    return optimize(input)


class DemandPipeline:
    def process(self, input: object) -> object:
        return process_demand(input)


__all__ = ("DemandPipeline", "process_demand")
