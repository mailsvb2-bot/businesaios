from __future__ import annotations

"""Ads bid adjustment heuristic. NOT the platform DecisionCore. optimize() here is bid-delta only; platform: core.ai.decision_core."""

from dataclasses import dataclass
from typing import Any, Dict, List
from config.scoring_behavior_policy import DEFAULT_BID_OPTIMIZATION_POLICY

Json = Dict[str, Any]


@dataclass(frozen=True)
class BidDecision:
    per_adgroup_delta_pct: Dict[str, int]
    notes: str = ""


class BidOptimizer:
    """Simple, safe bid adjustment heuristic.

    If CPA is too high -> decrease bids; if CPA good and budget under-spent -> increase.
    Deltas are capped.
    """

    def optimize(self, *, metrics: Json, adgroups: List[Json], target_cpa_minor: int) -> BidDecision:
        deltas: Dict[str, int] = {}
        t = int(target_cpa_minor or 0)
        if t <= 0:
            return BidDecision({}, notes="no_target")

        spend_minor = int(_get_int(metrics, ["spend_minor", "spend"], default=0))
        conv = int(_get_int(metrics, ["conversions", "leads"], default=0))
        cpa = (float(spend_minor) / float(conv)) if conv > 0 else float(spend_minor)

        policy = DEFAULT_BID_OPTIMIZATION_POLICY
        if conv <= 0:
            base = policy.no_conversion_delta_pct
        elif cpa >= float(t) * policy.high_cpa_multiplier:
            base = policy.high_cpa_delta_pct
        elif cpa <= float(t) * policy.low_cpa_multiplier:
            base = policy.low_cpa_delta_pct
        else:
            base = 0

        base = max(min(base, policy.delta_ceiling_pct), policy.delta_floor_pct)

        for a in adgroups or []:
            aid = str(a.get("id") or a.get("adgroup_id") or "")
            if not aid:
                continue
            deltas[aid] = base

        return BidDecision(deltas, notes="ok")


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
