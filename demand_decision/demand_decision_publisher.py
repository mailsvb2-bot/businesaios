from __future__ import annotations


class DemandDecisionPublisher:
    """Compatibility shell kept only to make the migration explicit.

    Final executable demand decisions must go through core.ai.decision_core.DecisionCore
    via demand_decision.canonical_decision_bridge.CanonicalDemandDecisionBridge.
    This class intentionally refuses to publish decisions so that the project
    cannot drift back into a parallel decision path.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._message = (
            'DemandDecisionPublisher is retired. Use CanonicalDemandDecisionBridge '
            'with core.ai.decision_core.DecisionCore for final demand decisions.'
        )

    def publish(self, *args, **kwargs):
        raise RuntimeError(self._message)
