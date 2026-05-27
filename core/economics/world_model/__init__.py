"""World model primitives for demand/price/conversion dynamics.

IMPORTANT:
- This package is PURE: it must not perform side-effects (network, DB writes, etc).
- It only provides *derived features* used by DecisionCore / pricing policies.
- Offline training + storage of parameters lives outside core (platform_layer / ml).
"""
from .conversion import ConversionModel, LogisticConversionModel
from .demand_curves import DemandCurveModel, IsoelasticDemandCurve, LinearDemandCurve, PiecewiseLinearDemandCurve
from .seasonality import DOWSeasonalityModel, SeasonalityModel
from .types import (
    ConversionObservation,
    DemandObservation,
    FunnelObservation,
    FunnelStage,
    MarketContext,
    PricePoint,
)
from .world_model import PricingWorldModel
from .world_state import PricingWorldState, WorldModelInput

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
