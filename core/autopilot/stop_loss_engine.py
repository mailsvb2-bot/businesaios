from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopLossConfig:
    max_cac_minor: int
    max_spend_no_conv_minor: int
    min_profit_minor: int


@dataclass(frozen=True)
class StopLossState:
    spend_minor: int
    conversions: int
    profit_minor: int
    cac_minor: int | None


@dataclass(frozen=True)
class StopLossDecision:
    triggered: bool
    reason: str | None = None


def evaluate_stop_loss(cfg: StopLossConfig, st: StopLossState) -> StopLossDecision:
    if st.profit_minor <= cfg.min_profit_minor:
        return StopLossDecision(True, "profit_below_threshold")
    if st.conversions == 0 and st.spend_minor >= cfg.max_spend_no_conv_minor:
        return StopLossDecision(True, "spend_without_conversions")
    if st.cac_minor is not None and st.cac_minor >= cfg.max_cac_minor:
        return StopLossDecision(True, "cac_above_threshold")
    return StopLossDecision(False, None)
