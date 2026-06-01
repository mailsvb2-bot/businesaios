from __future__ import annotations

from dataclasses import dataclass

from config.economics_world_model_policy import (
    DEFAULT_PRICING_WORLD_MODEL_POLICY,
    PricingWorldModelPolicy,
)

from .conversion import ConversionModel, LogisticConversionModel
from .demand_curves import DemandCurveModel, IsoelasticDemandCurve
from .seasonality import DOWSeasonalityModel, SeasonalityModel
from .world_state import PricingWorldState, WorldModelInput


@dataclass(frozen=True)
class PricingWorldModel:
    """Composite world model for pricing: demand curve + conversion + seasonality.

    IMPORTANT:
    - This model is PURE and deterministic once parameters are provided.
    - Loading and storing parameters is a platform concern outside core.
    """

    demand: DemandCurveModel
    conversion: ConversionModel
    seasonality: SeasonalityModel

    def build(self, inp: WorldModelInput) -> PricingWorldState:
        price = float(inp.current_price)
        season = float(self.seasonality.multiplier(dow=inp.context.dow, hour=inp.context.hour))
        demand_units = float(self.demand.predict_units(price=price)) * season
        conv = float(self.conversion.predict_prob(price=price))
        elasticity = float(self.demand.point_elasticity(price=price))
        revenue = price * demand_units
        marginal_cost = (
            float(inp.marginal_cost)
            if inp.marginal_cost is not None
            else DEFAULT_PRICING_WORLD_MODEL_POLICY.zero_marginal_cost
        )
        profit = float((price - marginal_cost) * demand_units)

        return PricingWorldState(
            demand_units_at_price=float(demand_units),
            conversion_prob_at_price=float(conv),
            point_elasticity=float(elasticity),
            seasonality_multiplier=float(season),
            expected_revenue=float(revenue),
            expected_profit=float(profit),
            demand_model=self.demand.__class__.__name__,
            conversion_model=self.conversion.__class__.__name__,
            seasonality_model=self.seasonality.__class__.__name__,
        )

    @staticmethod
    def default(
        *,
        policy: PricingWorldModelPolicy = DEFAULT_PRICING_WORLD_MODEL_POLICY,
    ) -> PricingWorldModel:
        return PricingWorldModel(
            demand=IsoelasticDemandCurve(
                a=policy.default_demand_scale,
                b=policy.default_demand_exponent,
            ),
            conversion=LogisticConversionModel(
                w0=policy.default_conversion_bias,
                w1=policy.default_conversion_slope,
            ),
            seasonality=DOWSeasonalityModel(mult={}),
        )
