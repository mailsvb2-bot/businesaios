from __future__ import annotations

from config.demand_scoring import ROUTING_POLICY_DELTAS
from registry.routing_policy_registry import RoutingPolicyRegistry
from routing.policies import (
    CapacityProtectionPolicy,
    FairRotationPolicy,
    FastResponsePolicy,
    GeoLocalityPolicy,
    HighRiskRequestPolicy,
    HighValueClientPolicy,
    NewBusinessRampPolicy,
    PremiumSupplyPolicy,
    ReputationSafetyPolicy,
)
from shared.numbers import coerce_float


class RouterPolicyEvaluator:
    def __init__(self) -> None:
        self._policies = RoutingPolicyRegistry()
        self._register_default_policies()

    def _register_default_policies(self) -> None:
        for policy in (
            HighValueClientPolicy(),
            GeoLocalityPolicy(),
            FastResponsePolicy(),
            CapacityProtectionPolicy(),
            PremiumSupplyPolicy(),
            FairRotationPolicy(),
            NewBusinessRampPolicy(),
            ReputationSafetyPolicy(),
            HighRiskRequestPolicy(),
        ):
            self._policies.register(getattr(policy, 'NAME', policy.__class__.__name__), policy)

    def evaluate(self, *, intent, profile, live_state) -> tuple[float, tuple[str, ...]]:
        delta = 0.0
        tags: list[str] = []
        for _, policy in self._policies.items():
            adj = coerce_float(policy.adjust(intent=intent, profile=profile, live_state=live_state), 0.0)
            if adj:
                tags.append(f"{policy.NAME}:{adj:+.3f}")
            delta += adj
        limit = max(
            ROUTING_POLICY_DELTAS.high_risk_penalty,
            ROUTING_POLICY_DELTAS.low_reputation_penalty,
        )
        return max(-limit, min(limit, delta)), tuple(tags)
