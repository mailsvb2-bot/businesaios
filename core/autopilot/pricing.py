"""Deterministic price recommendation (rule + bandit).

This module does NOT set prices; it only produces recommendations + reasons.
DecisionCore/policy decides whether to apply, and guardrails may block.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

@dataclass(frozen=True)
class PriceRecommendation:
    price_minor: int
    currency: str
    reason: str
    debug: Mapping[str, Any] | None = None


def recommend_price_minor(
    *,
    base_price_minor: int,
    currency: str,
    stats: Mapping[str, Any],
    seed: str,
    user_id: str,
    step_key: str = "autopilot_price",
) -> PriceRecommendation:
    """Recommend a price using deterministic Thompson sampling over 3 arms.

    Arms: down (-10%), keep, up (+10%).
    Stats format (optional):
      stats = {
        "down": {"alpha": 1.0, "beta": 1.0},
        "keep": {"alpha": 1.0, "beta": 1.0},
        "up": {"alpha": 1.0, "beta": 1.0},
      }
    """

    bp = int(base_price_minor)
    bp = 0 if bp < 0 else bp
    cur = str(currency or "RUB")

    # Stable RNG seed.
    h = hashlib.sha256(f"{seed}|{user_id}|{step_key}".encode()).digest()
    rng = random.Random(int.from_bytes(h[:8], "big", signed=False))

    def _ab(key: str) -> tuple[float, float]:
        raw = stats.get(key) if isinstance(stats.get(key), dict) else {}
        try:
            a = float(raw.get("alpha", 1.0))
            b = float(raw.get("beta", 1.0))
            return max(1e-6, a), max(1e-6, b)
        except Exception:
            return 1.0, 1.0

    arms = {
        "down": 0.9,
        "keep": 1.0,
        "up": 1.1,
    }

    scores: dict[str, float] = {}
    for k in arms:
        a, b = _ab(k)
        try:
            scores[k] = rng.betavariate(a, b)
        except Exception:
            scores[k] = 0.5

    choice = max(scores.items(), key=lambda kv: kv[1])[0]
    mult = float(arms[choice])
    price = int(round(bp * mult))

    # Rule safety: keep within sane bounds.
    floor = max(0, int(round(bp * 0.5)))
    ceil = int(round(bp * 2.0))
    if price < floor:
        price = floor
        choice = "down"
    if price > ceil:
        price = ceil
        choice = "up"

    return PriceRecommendation(
        price_minor=price,
        currency=cur,
        reason=f"bandit:{choice}",
        debug={"scores": scores, "base": bp, "floor": floor, "ceil": ceil},
    )
