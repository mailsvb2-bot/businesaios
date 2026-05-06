from __future__ import annotations

"""Off-policy evaluation (OPE) primitives for logged bandits.

We implement IPS and SNIPS estimators on a dataset where each row contains:
- reward
- behavior_propensity (prob of chosen action under logging policy)
- target_propensity (prob of chosen action under target policy)

The target policy is supplied as a callable that returns a probability for the
observed action given row context.

This is intentionally minimal and deterministic.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class OpeReport:
    ips: float
    snips: float
    n: int
    w_sum: float


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def evaluate_ips_snips(
    rows: Iterable[Dict[str, Any]],
    *,
    target_propensity: Callable[[Dict[str, Any]], float],
    behavior_propensity_key: str = "propensity",
    reward_key: str = "reward",
) -> OpeReport:
    w_r_sum = 0.0
    w_sum = 0.0
    n = 0

    for r in rows:
        if not isinstance(r, dict):
            continue
        b = _safe_float(r.get(behavior_propensity_key), 0.0)
        if not (b > 0.0):
            continue
        t = _safe_float(target_propensity(r), 0.0)
        if not (t >= 0.0):
            continue
        w = float(t) / float(b)
        rew = _safe_float(r.get(reward_key), 0.0)
        w_r_sum += float(w) * float(rew)
        w_sum += float(w)
        n += 1

    ips = float(w_r_sum) / float(max(1, n))
    snips = float(w_r_sum) / float(w_sum) if w_sum > 0.0 else 0.0
    return OpeReport(ips=float(ips), snips=float(snips), n=int(n), w_sum=float(w_sum))
