from __future__ import annotations

from dataclasses import dataclass

from ..types import EconomicsSnapshot


@dataclass
class UnitEconomicsProjection:
    def project(self, snapshot: EconomicsSnapshot) -> dict:
        unit = snapshot.unit_economics
        return {
            "snapshot_id": snapshot.snapshot_id.value,
            "gross_profit": unit.gross_profit,
            "contribution_profit": unit.contribution_profit,
            "contribution_margin_ratio": unit.contribution_margin_ratio,
            "revenue_per_customer": unit.revenue_per_customer,
            "contribution_per_customer_period": unit.contribution_per_customer_period,
            "contribution_per_customer_day": unit.contribution_per_customer_day,
            "variable_cost_ratio": unit.variable_cost_ratio,
        }
