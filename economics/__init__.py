"""Economics package."""

from shared.kinded_payloads import build_kinded_payload
from economics.demand_surface import (
    BusinessLtvByRoute,
    ChannelMixProfitability,
    CustomerAcquisitionCostByChannel,
    DemandMarginSnapshot,
    LeadUnitEconomics,
    MarketplaceTakeRate,
    RoutedLeadValue,
    RoutingProfitabilityEngine,
)

CANON_ECONOMICS_PACKAGE_OWNER = True

class BusinessGrowthSnapshot:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("business_growth_snapshot", payload)

class CacCalculator:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("cac_snapshot", payload)

class CampaignProfitability:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("campaign_profitability", payload)

class ChannelProfitability:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("channel_profitability", payload)

class LtvEstimator:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("ltv_snapshot", payload)

class ProfitEngine:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("profit_snapshot", payload)

class RevenueTracker:
    def track(self, payload: dict) -> dict:
        return build_kinded_payload("revenue_snapshot", payload)

class RoasCalculator:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("roas_snapshot", payload)

class RoiCalculator:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("roi_snapshot", payload)

__all__ = [
    "CANON_ECONOMICS_PACKAGE_OWNER",
    "BusinessGrowthSnapshot",
    "BusinessLtvByRoute",
    "CacCalculator",
    "CampaignProfitability",
    "ChannelMixProfitability",
    "ChannelProfitability",
    "CustomerAcquisitionCostByChannel",
    "DemandMarginSnapshot",
    "LeadUnitEconomics",
    "LtvEstimator",
    "MarketplaceTakeRate",
    "ProfitEngine",
    "RevenueTracker",
    "RoasCalculator",
    "RoiCalculator",
    "RoutedLeadValue",
    "RoutingProfitabilityEngine",
]
