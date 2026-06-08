from __future__ import annotations

"""Event-sourced RL-based pricing (production-hard).

This module provides a *deterministic*, event-sourced pricing policy suitable for
production use without mutable model state.

Design goals
- Pure: derives statistics from the canonical event stream only.
- Safe: bounded candidate grid + conservative fallbacks.
- OPE-ready: returns a well-defined propensity for the chosen price.
- Explainable: returns debug describing coverage, probabilities, and choice.

Signals (existing in this repo)
- offer_shown: impression with arm + price (trial)
- offer_outcome: success/failure outcome for offer_shown (reward proxy)
- tariff_selected / payment_captured: legacy signals (still supported)

We primarily use offer_shown/offer_outcome because it yields a clean logged
bandit dataset (impression -> outcome) even when the user does nothing.

Algorithm
- Build Beta posterior for conversion per price point.
- Compute expected revenue = price * posterior_mean_conversion.
- Choose with Softmax(expected_revenue / temperature) for known propensities.

NOTE: Thompson sampling has intractable exact propensities in general.
For production OPE and safe rollout, we prefer Softmax/epsilon-greedy variants
with explicit probabilities.
"""

import time
from dataclasses import dataclass
from typing import Any

from config.pricing_retention_policy import DEFAULT_RL_PRICING_DEFAULTS
from core.pricing.rl.candidates import build_candidates, clamp_int
from core.pricing.rl.evidence import collect_pricing_evidence
from core.pricing.rl.scoring import choose_candidate


@dataclass(frozen=True)
class RLPricingConfig:
    enabled: bool = False

    # Evidence horizon
    lookback_days: int = 30
    window_hours: int = 24  # used for legacy signals (tariff_selected/payment)

    # Candidate grid around base price
    grid_radius_pct: float = DEFAULT_RL_PRICING_DEFAULTS.grid_radius_pct
    grid_step_rub: int = 100

    # Safety bounds
    min_price_rub: int = 100
    max_price_rub: int = 999_999

    # Conservative Bayesian prior for conversion
    prior_alpha: float = DEFAULT_RL_PRICING_DEFAULTS.prior_alpha
    prior_beta: float = DEFAULT_RL_PRICING_DEFAULTS.prior_beta

    # Exploration
    seed_salt: str = "pricing_rl_v2"
    exploration: str = "softmax_v1"  # softmax_v1 | epsilon_greedy_v1
    temperature: float = DEFAULT_RL_PRICING_DEFAULTS.temperature
    epsilon: float = DEFAULT_RL_PRICING_DEFAULTS.epsilon


def _now_ms() -> int:
    return int(time.time() * 1000)


def _stable_rng(seed_material: str):
    # local import avoids global state
    import random

    return random.Random(seed_material)


def choose_price_rub(
    event_store: Any,
    *,
    tenant_id: str,
    offer_arm: str,
    base_price_rub: int,
    cfg: RLPricingConfig,
    now_ms: int | None = None,
    context_key: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Choose a price point for an offer_arm.

    Returns (price_rub, debug).

    Safe fallback: returns base_price_rub if disabled or insufficient data.
    """

    base = int(max(1, base_price_rub))
    debug: dict[str, Any] = {
        "enabled": bool(cfg.enabled),
        "offer_arm": str(offer_arm),
        "base_price_rub": int(base),
        "method": "rl_softmax_event_sourced_v2",
        "exploration": str(cfg.exploration),
        "policy_id": "pricing_rl_v2",
    }

    if not cfg.enabled:
        debug["note"] = "disabled"
        return int(base), debug

    now_ms = int(now_ms if now_ms is not None else _now_ms())
    start_ms = now_ms - int(max(1, cfg.lookback_days)) * 24 * 3600 * 1000
    end_ms = now_ms
    window_ms = int(max(1, cfg.window_hours)) * 3600 * 1000

    ctx = str(context_key or "").strip()
    if ctx:
        debug["context_key"] = ctx

    stats, evidence_debug = collect_pricing_evidence(
        event_store=event_store,
        tenant_id=str(tenant_id),
        offer_arm=str(offer_arm),
        start_ms=start_ms,
        end_ms=end_ms,
        window_ms=window_ms,
        context_key=ctx,
    )
    debug.update(evidence_debug)

    if debug.get("trials", 0) == 0:
        debug["note"] = "no_trials"
        return int(base), debug

    succ_total = int(debug.get("successes", 0) or 0)
    if succ_total == 0:
        debug["note"] = "no_successes"
        return int(base), debug

    candidates = build_candidates(
        base_price_rub=base,
        grid_radius_pct=float(cfg.grid_radius_pct),
        grid_step_rub=int(cfg.grid_step_rub),
        min_price_rub=int(cfg.min_price_rub),
        max_price_rub=int(cfg.max_price_rub),
        observed_stats=stats,
    )

    if len(candidates) <= 1:
        debug["note"] = "single_candidate"
        return int(candidates[0] if candidates else base), debug

    day = now_ms // (24 * 3600 * 1000)
    seed_material = f"{cfg.seed_salt}|{tenant_id}|{offer_arm}|{ctx}|{day}"
    rng = _stable_rng(seed_material)

    selected = choose_candidate(
        rng=rng,
        candidates=candidates,
        stats=stats,
        exploration=str(cfg.exploration or "softmax_v1"),
        epsilon=float(cfg.epsilon),
        temperature=float(cfg.temperature),
        prior_alpha=float(cfg.prior_alpha),
        prior_beta=float(cfg.prior_beta),
    )

    debug["candidates"] = [int(x) for x in candidates]
    debug["posterior_mean_conv"] = {
        str(int(p)): float(m) for p, m in zip(candidates, selected["means"], strict=False)
    }
    debug["expected_revenue"] = {
        str(int(p)): float(r)
        for p, r in zip(candidates, selected["expected_revenue"], strict=False)
    }
    debug["probs"] = {
        str(int(p)): float(pr) for p, pr in zip(candidates, selected["probs"], strict=False)
    }
    debug["choice"] = int(
        clamp_int(int(selected["choice"]), int(cfg.min_price_rub), int(cfg.max_price_rub))
    )
    debug["propensity"] = selected["propensity"]
    debug["note"] = "ok"

    return int(debug["choice"]), debug
