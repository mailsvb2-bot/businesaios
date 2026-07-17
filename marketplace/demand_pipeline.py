from __future__ import annotations

from core.ai import get_decision_core_singleton
from core.strategic_horizon.engine import CANONICAL_DECISION_OPTIMIZE_METHOD
from runtime.decision_gateway import optimize_runtime_decision


def process_demand(input: object) -> object:
    """Single canonical demand execution contract."""

    return optimize_runtime_decision(
        issuer=get_decision_core_singleton(),
        state=input,
        method_name=CANONICAL_DECISION_OPTIMIZE_METHOD,
    )


class DemandPipeline:
    def process(self, input: object) -> object:
        return process_demand(input)


__all__ = ("DemandPipeline", "process_demand")
