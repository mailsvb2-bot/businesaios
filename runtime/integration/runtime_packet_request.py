from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from runtime.advisory.autonomy_advisory_packet import AutonomyAdvisoryPacket
from runtime.market.market_snapshot import MarketSnapshot


@dataclass(frozen=True)
class RuntimePacketRequest:
    generated_at_ms: int
    user_observables: Mapping[str, object]
    market_snapshot: MarketSnapshot
    creative_snapshots: tuple[object, ...]
    architecture_state: Mapping[str, float]
    structure_state: Mapping[str, float]
    flow_state: Mapping[str, float]
    diffusion_state: Mapping[str, float]
    advisory_packet: AutonomyAdvisoryPacket
