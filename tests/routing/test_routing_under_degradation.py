from __future__ import annotations

from execution.routing.capability_quarantine import CapabilityQuarantine
from execution.routing.capability_registry import CapabilityRegistry, CapabilityRoute
from execution.routing.capability_router import CapabilityRouter


def test_routing_under_degradation_falls_back_when_primary_quarantined() -> None:
    registry = CapabilityRegistry()
    registry.register_many(
        [
            CapabilityRoute(
                route_key='mail_primary',
                capability_key='communications_write',
                supported_action_types=('send_email',),
                maturity='real',
                enabled=True,
                base_cost=2.0,
                base_latency_ms=300.0,
                base_proofability=0.9,
                health_score=0.95,
            ),
            CapabilityRoute(
                route_key='mail_secondary',
                capability_key='communications_write',
                supported_action_types=('send_email',),
                maturity='real',
                enabled=True,
                base_cost=4.0,
                base_latency_ms=500.0,
                base_proofability=0.8,
                health_score=0.80,
            ),
        ]
    )
    quarantine = CapabilityQuarantine()
    quarantine.quarantine(route_key='mail_primary', reason='incident', ttl_seconds=60.0)

    router = CapabilityRouter(registry=registry, quarantine=quarantine)
    decision = router.select_best_route(
        capability_key='communications_write',
        action_type='send_email',
        requested_units=1.0,
    )

    assert decision.selected_route is not None
    assert decision.selected_route.route_key == 'mail_secondary'
    assert decision.explanation.selected_route_key == 'mail_secondary'
    assert decision.explanation.factors['rejected_routes']['mail_primary'] == 'route_quarantined'
