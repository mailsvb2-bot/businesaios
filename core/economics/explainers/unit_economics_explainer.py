from __future__ import annotations

from dataclasses import dataclass

from ..types import EconomicsSnapshot, UnitEconomicsSnapshot


@dataclass
class UnitEconomicsExplainer:
    def explain(self, snapshot: EconomicsSnapshot) -> str:
        unit = snapshot.unit_economics
        return (
            f"Gross profit={unit.gross_profit:.2f}, "
            f"contribution profit={unit.contribution_profit:.2f}, "
            f"contribution margin={unit.contribution_margin_ratio:.2%}, "
            f"revenue/customer={unit.revenue_per_customer:.2f}."
        )


def explain_unit_economics(snapshot: UnitEconomicsSnapshot) -> str:
    return f"cac={snapshot.cac}; ltv={snapshot.ltv}; margin={snapshot.margin}"
