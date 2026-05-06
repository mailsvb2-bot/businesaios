from __future__ import annotations

"""Offline trainer for pricing world model parameters.

This is intentionally lightweight and dependency-free (no numpy).
It can run in CI and local dev environments.

Inputs are aggregated observations (already privacy-filtered and tenant-scoped).
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Sequence

from core.economics.world_model.conversion import LogisticConversionModel
from core.economics.world_model.demand_curves import IsoelasticDemandCurve, PiecewiseLinearDemandCurve
from core.economics.world_model.seasonality import DOWSeasonalityModel
from core.economics.world_model.serialize import pricing_world_model_to_dict
from core.economics.world_model.types import ConversionObservation, DemandObservation
from core.economics.world_model.world_model import PricingWorldModel


@dataclass(frozen=True)
class WorldModelTrainConfig:
    demand_kind: str = "isoelastic"  # isoelastic|piecewise_linear
    piecewise_k: int = 6
    l2: float = 1e-6


def train_pricing_world_model(
    *,
    demand_obs: Sequence[DemandObservation],
    conv_obs: Sequence[ConversionObservation],
    config: WorldModelTrainConfig = WorldModelTrainConfig(),
) -> PricingWorldModel:
    dk = str(config.demand_kind).strip().lower()
    if dk == "piecewise_linear":
        demand = PiecewiseLinearDemandCurve.calibrate(demand_obs, k=int(config.piecewise_k))
    else:
        demand = IsoelasticDemandCurve.calibrate(demand_obs)

    conversion = LogisticConversionModel.calibrate(conv_obs, l2=float(config.l2))
    seasonality = DOWSeasonalityModel.calibrate(demand_obs)

    return PricingWorldModel(demand=demand, conversion=conversion, seasonality=seasonality)


def export_pricing_world_model_payload(model: PricingWorldModel) -> Dict[str, Any]:
    """Serialize to a governed JSON payload for registries/stores."""
    return pricing_world_model_to_dict(model)


def train_and_export_payload(
    *,
    demand_obs: Sequence[DemandObservation],
    conv_obs: Sequence[ConversionObservation],
    config: WorldModelTrainConfig = WorldModelTrainConfig(),
) -> Dict[str, Any]:
    model = train_pricing_world_model(demand_obs=demand_obs, conv_obs=conv_obs, config=config)
    return export_pricing_world_model_payload(model)
