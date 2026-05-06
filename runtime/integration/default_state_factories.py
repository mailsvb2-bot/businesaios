from __future__ import annotations

from runtime.advisory.autonomy_advisory_packet import AutonomyAdvisoryPacket
from runtime.market.market_snapshot import MarketSnapshot


def default_market_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        global_macro_score=0.50,
        global_micro_score=0.50,
        global_competitive_shift=0.50,
        segment_states=(),
    )


def default_architecture_state() -> dict[str, float]:
    return {"global_stability": 0.50}


def default_structure_state() -> dict[str, float]:
    return {
        "curvature": 0.50,
        "boundary_pressure": 0.50,
        "blast_radius_risk": 0.50,
    }


def default_flow_state() -> dict[str, float]:
    return {
        "velocity": 0.50,
        "pressure": 0.50,
        "turbulence": 0.50,
    }


def default_diffusion_state() -> dict[str, float]:
    return {
        "spread_index": 0.50,
        "saturation_risk": 0.50,
        "viral_potential": 0.50,
    }


def default_user_observables() -> dict[str, float]:
    return {
        "intent_index": 0.50,
        "trust_index": 0.50,
        "value_index": 0.50,
        "payment_readiness_index": 0.50,
        "fatigue_index": 0.50,
        "hesitation_score": 0.50,
        "buy_vector": 0.50,
        "churn_vector": 0.50,
        "coherence_score": 0.50,
    }


def default_advisory_packet() -> AutonomyAdvisoryPacket:
    return AutonomyAdvisoryPacket(packet_name="autonomy_advisory_v1", recommendations=(), notes=())
