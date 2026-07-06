from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from runtime.market.market_snapshot import MarketSnapshot
from runtime.state import apply_synthesized_world_view


@dataclass(frozen=True)
class FallbackPolicy:
    allow_missing_user_observables: bool = False
    allow_missing_market_snapshot: bool = False
    allow_missing_architecture_state: bool = False
    allow_missing_structure_state: bool = False
    allow_missing_flow_state: bool = False
    allow_missing_diffusion_state: bool = False
    allow_missing_advisory_packet: bool = False


STRICT_FALLBACK_POLICY = FallbackPolicy()

TEST_FALLBACK_POLICY = FallbackPolicy(
    allow_missing_user_observables=True,
    allow_missing_market_snapshot=True,
    allow_missing_architecture_state=True,
    allow_missing_structure_state=True,
    allow_missing_flow_state=True,
    allow_missing_diffusion_state=True,
    allow_missing_advisory_packet=True,
)





def apply_world_view_with_policy(
    *,
    snapshot: object,
    user_observables: Mapping[str, object],
    market_snapshot: MarketSnapshot,
    architecture_state: Mapping[str, float],
    structure_state: Mapping[str, float],
    flow_state: Mapping[str, float],
    diffusion_state: Mapping[str, float],
) -> tuple[dict[str, object], MarketSnapshot, dict[str, float], dict[str, float], dict[str, float], dict[str, float]]:
    return apply_synthesized_world_view(
        snapshot=snapshot,
        fallback_user_observables=dict(user_observables),
        fallback_market_snapshot=market_snapshot,
        fallback_architecture_state=dict(architecture_state),
        fallback_structure_state=dict(structure_state),
        fallback_flow_state=dict(flow_state),
        fallback_diffusion_state=dict(diffusion_state),
    )


__all__ = [
    'FallbackPolicy',
    'STRICT_FALLBACK_POLICY',
    'TEST_FALLBACK_POLICY',
    'apply_world_view_with_policy',
]
