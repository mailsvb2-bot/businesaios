from __future__ import annotations

"""Guardrails for business autopilot.

These functions are deterministic and side-effect free.
"""

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from contracts.autopilot_contract import AutopilotContract


def _to_int(v: object, *, default: int = 0) -> int:
    """Best-effort int conversion (deterministic, no logging)."""
    try:
        return int(v)
    except Exception:
        return int(default)


@dataclass(frozen=True)
class GuardrailVerdict:
    allow: bool
    reason: str = ""
    details: Mapping[str, Any] | None = None


def evaluate_stop_loss(*, contract: AutopilotContract, metrics: Mapping[str, Any]) -> GuardrailVerdict:
    """Stop-loss based on read-model metrics.

    metrics keys (best-effort):
      profit_minor_today
      cac_minor_today
    """
    try:
        profit = _to_int(metrics.get("profit_minor_today") or 0)
    except Exception:
        profit = 0
    try:
        cac = _to_int(metrics.get("cac_minor_today") or 0)
    except Exception:
        cac = 0

    _ = contract.safety_policy
    return evaluate_stop_loss_window(contract=contract, window=[{"profit_minor": profit, "cac_minor": cac}])


def evaluate_stop_loss_window(*, contract: AutopilotContract, window: list[Mapping[str, Any]]) -> GuardrailVerdict:
    """Stop-loss evaluated over a rolling window.

    Window items may contain (best-effort):
      profit_minor, cac_minor, spend_minor, conversions
    """

    s = contract.safety_policy
    w = [x for x in (window or []) if isinstance(x, Mapping)]
    if not w:
        return GuardrailVerdict(True, "OK")

    # CAC guard: if any day in last N days violates limit -> stop.
    cac_days = max(1, int(getattr(s, "stop_loss_cac_days", 1) or 1))
    if int(s.stop_loss_max_cac_minor) > 0:
        for it in w[-cac_days:]:
            try:
                cac_v = _to_int(it.get("cac_minor") or it.get("cac_minor_today") or 0)
            except Exception:
                cac_v = 0
            if cac_v > int(s.stop_loss_max_cac_minor):
                return GuardrailVerdict(False, "STOP_LOSS_CAC", {"cac_minor": cac_v, "limit": int(s.stop_loss_max_cac_minor), "days": cac_days})

    # Profit guard: if profit below (negative threshold) for N consecutive days -> stop.
    profit_days = max(1, int(getattr(s, "stop_loss_profit_days", 1) or 1))
    if int(s.stop_loss_min_profit_minor) < 0:
        streak = 0
        last_prof = 0
        for it in w[-profit_days:]:
            try:
                last_prof = _to_int(it.get("profit_minor") or it.get("profit_minor_today") or 0)
            except Exception:
                last_prof = 0
            if last_prof < int(s.stop_loss_min_profit_minor):
                streak += 1
            else:
                streak = 0
        if streak >= profit_days:
            return GuardrailVerdict(False, "STOP_LOSS_PROFIT", {"profit_minor": last_prof, "limit": int(s.stop_loss_min_profit_minor), "days": profit_days})

    # Ads-style stop-loss: if spend exceeds threshold in window and conversions==0.
    max_spend = int(getattr(s, "stop_loss_max_spend_minor_no_conv", 0) or 0)
    if max_spend > 0:
        nd = max(1, int(getattr(s, "stop_loss_no_conv_days", 1) or 1))
        spend = 0
        conv = 0
        for it in w[-nd:]:
            spend += _to_int(it.get("spend_minor") or 0)
            conv += _to_int(it.get("conversions") or 0)
        if spend >= max_spend and conv <= 0:
            return GuardrailVerdict(False, "STOP_LOSS_NO_CONV", {"spend_minor": int(spend), "limit": int(max_spend), "days": nd})

    return GuardrailVerdict(True, "OK")


def enforce_change_rate(*, contract: AutopilotContract, changes_today: int) -> GuardrailVerdict:
    lim = int(contract.constraints.max_price_changes_per_day)
    if int(changes_today) >= lim:
        return GuardrailVerdict(False, "MAX_CHANGES_PER_DAY", {"changes_today": int(changes_today), "limit": lim})
    return GuardrailVerdict(True, "OK")
