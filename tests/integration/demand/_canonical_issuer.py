from __future__ import annotations

from types import SimpleNamespace

from core.ai import set_decision_core_singleton
from core.policies.demand_route_policy import DemandRoutePolicyV1


class CanonicalDemandPolicyIssuer:
    """Test issuer that delegates all route selection to the Canon policy."""

    def __init__(self) -> None:
        self.states: list[object] = []

    def issue(self, state):
        self.states.append(state)
        proposed = DemandRoutePolicyV1().propose(state)
        session = getattr(state, "session", None) or {}
        request_id = str(session.get("request_id") or "demand-request")
        return SimpleNamespace(
            decision=SimpleNamespace(
                action=proposed.action,
                payload=proposed.payload,
                decision_id=f"signed-demand-route:{request_id}",
                correlation_id=request_id,
            )
        )


def build_registered_demand_policy_issuer() -> CanonicalDemandPolicyIssuer:
    issuer = CanonicalDemandPolicyIssuer()
    set_decision_core_singleton(issuer)
    return issuer


__all__ = [
    "CanonicalDemandPolicyIssuer",
    "build_registered_demand_policy_issuer",
]
