from __future__ import annotations

from dataclasses import dataclass


class BusinessLtvByRoute:
    def compute(self, repeat_rate: float, margin: float, avg_order_value: float) -> float:
        return float(repeat_rate) * float(margin) * float(avg_order_value) * 4.0


class ChannelMixProfitability:
    def summarize(self, rows: tuple[dict[str, object], ...]) -> dict[str, float]:
        out: dict[str, float] = {}
        for row in rows:
            ch = str(row.get('channel') or 'unknown')
            out[ch] = out.get(ch, 0.0) + float(row.get('contribution') or 0.0)
        return out


class CustomerAcquisitionCostByChannel:
    def compute(self, spend: float, customers: int) -> float:
        return float(spend) / max(1, int(customers))


@dataclass(frozen=True, slots=True)
class DemandMarginSnapshot:
    gross_value: float
    acquisition_cost: float
    contribution: float


class LeadUnitEconomics:
    def compute(self, revenue: float, acquisition_cost: float) -> dict[str, float]:
        return {'contribution': float(revenue) - float(acquisition_cost)}


class MarketplaceTakeRate:
    def compute(self, platform_fee: float, gross_value: float) -> float:
        return float(platform_fee) / max(1.0, float(gross_value))


class RoutedLeadValue:
    def compute(self, close_rate: float, avg_order_value: float) -> float:
        return float(close_rate) * float(avg_order_value)


class RoutingProfitabilityEngine:
    def evaluate(self, expected_revenue: float, expected_cost: float, quality_score: float) -> float:
        return max(0.0, expected_revenue - expected_cost) * max(0.0, min(1.0, quality_score))


__all__ = [
    'BusinessLtvByRoute',
    'ChannelMixProfitability',
    'CustomerAcquisitionCostByChannel',
    'DemandMarginSnapshot',
    'LeadUnitEconomics',
    'MarketplaceTakeRate',
    'RoutedLeadValue',
    'RoutingProfitabilityEngine',
]
