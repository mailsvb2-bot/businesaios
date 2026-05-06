from __future__ import annotations

"""Offline trainer for pricing policies.

This trainer consumes PricingDataset rows (see ml/pricing_dataset.py) and produces
an interpretable policy artifact:

- For each (offer_arm, segment) choose the price with maximum estimated expected
  reward (mean reward).

This is a deliberately simple baseline that works with small data and remains
transparent.

The produced policy format is JSON-serializable dict:
{
  "type": "pricing_policy_tabular_v1",
  "default": {"offer_arm": {"price_rub": int}},
  "segments": {
      "segment_key": {"offer_arm": {"price_rub": int}}
  }
}

The policy can be evaluated offline with OPE primitives.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class TrainResult:
    policy: Dict[str, Any]
    metrics: Dict[str, float]


def train_tabular_policy(rows: Iterable[Dict[str, Any]]) -> TrainResult:
    # Aggregate mean reward per (segment, offer_arm, price)
    sums: Dict[Tuple[str, str, int], float] = {}
    cnts: Dict[Tuple[str, str, int], int] = {}

    for r in rows:
        if not isinstance(r, dict):
            continue
        seg = str(r.get("segment") or "").strip()
        arm = str(r.get("offer_arm") or "").strip()
        price = int(r.get("chosen_price_rub") or 0)
        if not arm or price <= 0:
            continue
        rew = float(r.get("reward") or 0.0)
        k = (seg, arm, price)
        sums[k] = float(sums.get(k, 0.0)) + float(rew)
        cnts[k] = int(cnts.get(k, 0)) +1

    # Choose best per (seg, arm)
    best: Dict[Tuple[str, str], Tuple[int, float, int]] = {}
    for (seg, arm, price), s in sums.items():
        n = int(cnts.get((seg, arm, price), 0))
        if n <= 0:
            continue
        mean = float(s) / float(n)
        key = (seg, arm)
        cur = best.get(key)
        if cur is None or mean > float(cur[1]):
            best[key] = (int(price), float(mean), int(n))

    # Build policy
    segments: Dict[str, Dict[str, Dict[str, int]]] = {}
    defaults: Dict[str, Dict[str, int]] = {}

    for (seg, arm), (price, mean, n) in best.items():
        if seg:
            segments.setdefault(seg, {})[arm] = {"price_rub": int(price)}
        else:
            defaults[arm] = {"price_rub": int(price)}

    policy: Dict[str, Any] = {
        "type": "pricing_policy_tabular_v1",
        "default": defaults,
        "segments": segments,
    }

    means = [float(v[1]) for v in best.values()] if best else []
    metrics = {
        "n_rules": float(len(best)),
        "mean_rule_reward": float(sum(means) / max(1, len(means))) if means else 0.0,
    }
    return TrainResult(policy=policy, metrics=metrics)


def target_propensity_from_tabular(policy: Dict[str, Any]):
    """Return a callable compatible with ml.ope.evaluate_ips_snips.

    The returned function assigns probability 1.0 if the observed chosen_price
    matches the policy's selected price for (segment, offer_arm), else 0.0.
    """

    defaults = dict(policy.get("default") or {})
    segments = dict(policy.get("segments") or {})

    def _f(row: Dict[str, Any]) -> float:
        seg = str(row.get("segment") or "").strip()
        arm = str(row.get("offer_arm") or "").strip()
        chosen = int(row.get("chosen_price_rub") or 0)
        if not arm or chosen <= 0:
            return 0.0

        rule = None
        if seg and seg in segments:
            rule = (segments.get(seg) or {}).get(arm)
        if rule is None:
            rule = defaults.get(arm)
        if not isinstance(rule, dict):
            return 0.0
        price = int(rule.get("price_rub") or 0)
        return 1.0 if price == chosen else 0.0

    return _f
