from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

Json = Dict[str, Any]


@dataclass(frozen=True)
class StopLossDecision:
    allowed: bool
    reason: str
    snapshot: Json


class StopLossGuard:
    """Deterministic stop-loss evaluation.

    Input is a metrics snapshot from AdsService.metrics() or a normalized read-model.
    """

    def __init__(self, *, max_spend_minor: int, max_cpa_minor: int, min_roas_x1000: int) -> None:
        self._max_spend_minor = int(max_spend_minor or 0)
        self._max_cpa_minor = int(max_cpa_minor or 0)
        self._min_roas_x1000 = int(min_roas_x1000 or 0)

    def evaluate(self, metrics: Json) -> StopLossDecision:
        snap = dict(metrics or {})
        spend_minor = int(_get_int(snap, ["spend_minor", "spend", "cost_minor"], default=0))
        conv = int(_get_int(snap, ["conversions", "leads"], default=0))
        revenue_minor = int(_get_int(snap, ["revenue_minor", "revenue"], default=0))

        # Spend cap
        if self._max_spend_minor > 0 and spend_minor >= self._max_spend_minor:
            return StopLossDecision(False, "max_spend_reached", {"spend_minor": spend_minor, "conversions": conv, "revenue_minor": revenue_minor})

        # CPA cap (only if conversions present)
        if self._max_cpa_minor > 0 and conv > 0:
            cpa = spend_minor // max(conv, 1)
            if cpa >= self._max_cpa_minor:
                return StopLossDecision(False, "max_cpa_reached", {"spend_minor": spend_minor, "conversions": conv, "cpa_minor": cpa})

        # ROAS floor: only checked when spend > 0.
        # FIX: removed `revenue_minor > 0` condition — zero revenue with spend also
        # means ROAS = 0 which is below any minimum ROAS threshold.
        if self._min_roas_x1000 > 0 and spend_minor > 0:
            roas_x1000 = (revenue_minor * 1000) // max(spend_minor, 1)
            if roas_x1000 < self._min_roas_x1000:
                return StopLossDecision(False, "min_roas_not_met", {"spend_minor": spend_minor, "revenue_minor": revenue_minor, "roas_x1000": roas_x1000})

        return StopLossDecision(True, "ok", {"spend_minor": spend_minor, "conversions": conv, "revenue_minor": revenue_minor})


def _get_int(d: Json, keys: list[str], *, default: int = 0) -> int:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            continue
    return int(default)
