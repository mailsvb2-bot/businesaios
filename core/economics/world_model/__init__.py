"""World model primitives for demand/price/conversion dynamics.

IMPORTANT:
- This package is PURE: it must not perform side-effects (network, DB writes, etc).
- It only provides *derived features* used by DecisionCore / pricing policies.
- Offline training + storage of parameters lives outside core (platform_layer / ml).
"""
from .types import (
    MarketContext,
    PricePoint,
    DemandObservation,
    ConversionObservation,
    FunnelStage,
    FunnelObservation,
)
from .demand_curves import DemandCurveModel, IsoelasticDemandCurve, LinearDemandCurve, PiecewiseLinearDemandCurve
from .conversion import ConversionModel, LogisticConversionModel
from .seasonality import SeasonalityModel, DOWSeasonalityModel
from .world_state import PricingWorldState, WorldModelInput
from .world_model import PricingWorldModel

__all__ = [
    "MarketContext",
    "PricePoint",
    "DemandObservation",
    "ConversionObservation",
    "FunnelStage",
    "FunnelObservation",
    "DemandCurveModel",
    "IsoelasticDemandCurve",
    "LinearDemandCurve",
    "PiecewiseLinearDemandCurve",
    "ConversionModel",
    "LogisticConversionModel",
    "SeasonalityModel",
    "DOWSeasonalityModel",
    "WorldModelInput",
    "PricingWorldState",
    "PricingWorldModel",
]