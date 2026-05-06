from __future__ import annotations

from execution.routing.capability_quarantine import CapabilityQuarantine
from execution.routing.capability_registry import CapabilityRegistry, CapabilityRoute
from execution.routing.capability_router import CapabilityRouter


def test_best_path_selection_prefers_health_and_proofability() -> None:
    registry = CapabilityRegistry()
    registry.register_many(
        [
            CapabilityRoute(
                route_key='ads_google',
                capability_key='ads_write',
                supported_action_types=('launch_campaign',),
                maturity='real',
                enabled=True,
                base_cost=3.0,
                base_latency_ms=400.0,
                base_proofability=0.95,
                health_score=0.92,
            ),
            CapabilityRoute(
                route_key='ads_backup',
                capability_key='ads_write',
                supported_action_types=('launch_campaign',),
                maturity='capability_shell',
                enabled=True,
                base_cost=1.0,
                base_latency_ms=300.0,
                base_proofability=0.40,
                health_score=0.70,
            ),
        ]
    )
    router = CapabilityRouter(registry=registry, quarantine=CapabilityQuarantine())

    decision = router.select_best_route(
        capability_key='ads_write',
        action_type='launch_campaign',
        requested_units=1.0,
    )

    assert decision.selected_route is not None
    assert decision.selected_route.route_key == 'ads_google'
    assert decision.alternatives
    assert decision.explanation.selected_route_key == 'ads_google'
