from __future__ import annotations

from dataclasses import dataclass

from ..types import EconomicsSnapshot


@dataclass
class MarginRiskExplainer:
    def explain(self, snapshot: EconomicsSnapshot) -> str:
        margin = snapshot.margin
        payback = snapshot.payback
        ltv = snapshot.ltv
        cac = snapshot.cac
        ratio_text = "unknown"
        if ltv.ltv is not None and cac.blended_cac not in (None, 0):
            ratio_text = f"{ltv.ltv / cac.blended_cac:.2f}"
        return (
            f"Net margin={margin.net_margin_ratio:.2%}, "
            f"gross margin={margin.gross_margin_ratio:.2%}, "
            f"payback_days={payback.cac_payback_days}, "
            f"LTV/CAC={ratio_text}."
        )
