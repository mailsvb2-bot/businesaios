from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from config.retention_pricing_flow_policy import (
    DEFAULT_RETENTION_PRICING_FLOW_POLICY,
    RetentionPricingFlowPolicy,
)
from core.observability.throttled_logger import exception_throttled
from core.pricing.rl.candidates import build_candidates
from core.pricing.rl.evidence import collect_pricing_evidence
from core.pricing.rl.scoring import posterior_mean_conv
from core.pricing.stop_loss import StopLossConfig, should_apply_price
from core.scorers.pricing import choose_probabilities

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionPriceEvidence:
    """One price candidate plus read-only evidence for DecisionCore ranking."""

    price_rub: int
    posterior_mean_conversion: float
    expected_revenue_rub: float
    propensity: float | None
    is_base: bool
    stoploss_allowed: bool
    debug: dict[str, Any]


def pricing_context_key(telemetry: dict | None) -> str:
    value = telemetry or {}
    return str(
        value.get("traffic_source")
        or value.get("utm_source")
        or value.get("channel")
        or value.get("source")
        or ""
    ).strip()


def _rl_config(*, env_int, env_float, policy: RetentionPricingFlowPolicy) -> dict[str, Any]:
    return {
        "enabled": bool(env_int("PRICING_RL_ENABLED", int(policy.rl_enabled_default))),
        "lookback_days": int(env_int("PRICING_RL_LOOKBACK_DAYS", int(policy.rl_lookback_days))),
        "window_hours": int(env_int("PRICING_RL_WINDOW_HOURS", int(policy.rl_window_hours))),
        "grid_radius_pct": float(
            env_float("PRICING_RL_GRID_RADIUS_PCT", float(policy.rl_grid_radius_pct))
        ),
        "grid_step_rub": int(env_int("PRICING_RL_GRID_STEP_RUB", int(policy.rl_grid_step_rub))),
        "min_price_rub": int(env_int("PRICING_RL_MIN_PRICE_RUB", int(policy.rl_min_price_rub))),
        "max_price_rub": int(env_int("PRICING_RL_MAX_PRICE_RUB", int(policy.rl_max_price_rub))),
    }


def _stoploss_config(*, env_int, env_float, policy: RetentionPricingFlowPolicy) -> StopLossConfig:
    return StopLossConfig(
        enabled=bool(
            env_int("PRICING_RL_STOPLOSS_ENABLED", int(policy.stoploss_enabled_default))
        ),
        lookback_hours=int(
            env_int("PRICING_RL_STOPLOSS_LOOKBACK_HOURS", int(policy.stoploss_lookback_hours))
        ),
        min_trials=int(env_int("PRICING_RL_STOPLOSS_MIN_TRIALS", int(policy.stoploss_min_trials))),
        max_conv_drop_pct=float(
            env_float(
                "PRICING_RL_STOPLOSS_MAX_CONV_DROP_PCT",
                float(policy.stoploss_max_conv_drop_pct),
            )
        ),
        max_rev_drop_pct=float(
            env_float(
                "PRICING_RL_STOPLOSS_MAX_REV_DROP_PCT",
                float(policy.stoploss_max_rev_drop_pct),
            )
        ),
        cooldown_hours=int(
            env_int("PRICING_RL_STOPLOSS_COOLDOWN_HOURS", int(policy.stoploss_cooldown_hours))
        ),
    )


def _base_candidate(*, base_price_rub: int, note: str, debug: dict[str, Any]) -> RetentionPriceEvidence:
    payload = dict(debug)
    payload["note"] = str(note)
    return RetentionPriceEvidence(
        price_rub=int(base_price_rub),
        posterior_mean_conversion=0.0,
        expected_revenue_rub=0.0,
        propensity=None,
        is_base=True,
        stoploss_allowed=True,
        debug=payload,
    )


def build_price_candidates(
    *,
    store: Any,
    tenant_id: str,
    offer_arm: str,
    base_price_rub: int | None,
    now_ms: int,
    pricing_ctx: str,
    env_int,
    env_float,
    policy: RetentionPricingFlowPolicy = DEFAULT_RETENTION_PRICING_FLOW_POLICY,
) -> list[RetentionPriceEvidence]:
    """Return admissible prices without choosing one.

    RL evidence and stop-loss remain fully active, but final ranking belongs to
    DecisionCore. The function performs no writes and emits no events.
    """

    if base_price_rub is None:
        return []
    base = max(1, int(base_price_rub))
    config = _rl_config(env_int=env_int, env_float=env_float, policy=policy)
    common_debug: dict[str, Any] = {
        "enabled": bool(config["enabled"]),
        "offer_arm": str(offer_arm),
        "base_price_rub": int(base),
        "method": "pricing_evidence_event_sourced_v3",
        "policy_id": "pricing_rl_v2",
    }
    context_key = str(pricing_ctx or "").strip()
    if context_key:
        common_debug["context_key"] = context_key
    if not config["enabled"]:
        return [_base_candidate(base_price_rub=base, note="disabled", debug=common_debug)]

    start_ms = int(now_ms) - max(1, int(config["lookback_days"])) * 24 * 3600 * 1000
    stats, evidence_debug = collect_pricing_evidence(
        event_store=store,
        tenant_id=str(tenant_id),
        offer_arm=str(offer_arm),
        start_ms=start_ms,
        end_ms=int(now_ms),
        window_ms=max(1, int(config["window_hours"])) * 3600 * 1000,
        context_key=context_key,
    )
    common_debug.update(evidence_debug)
    if int(common_debug.get("trials", 0) or 0) == 0:
        return [_base_candidate(base_price_rub=base, note="no_trials", debug=common_debug)]
    if int(common_debug.get("successes", 0) or 0) == 0:
        return [_base_candidate(base_price_rub=base, note="no_successes", debug=common_debug)]

    prices = build_candidates(
        base_price_rub=base,
        grid_radius_pct=float(config["grid_radius_pct"]),
        grid_step_rub=int(config["grid_step_rub"]),
        min_price_rub=int(config["min_price_rub"]),
        max_price_rub=int(config["max_price_rub"]),
        observed_stats=stats,
    )
    if len(prices) <= 1:
        only = int(prices[0] if prices else base)
        return [
            _base_candidate(
                base_price_rub=only,
                note="single_candidate",
                debug=common_debug,
            )
        ]

    means = [
        posterior_mean_conv(
            stats=stats,
            price=price,
            prior_alpha=1.0,
            prior_beta=19.0,
        )
        for price in prices
    ]
    expected_revenue = [
        float(price) * float(mean)
        for price, mean in zip(prices, means, strict=False)
    ]
    probabilities = choose_probabilities(
        exploration="softmax_v1",
        expected_revenue=expected_revenue,
        epsilon=0.05,
        temperature=1.0,
    )
    stoploss = _stoploss_config(env_int=env_int, env_float=env_float, policy=policy)
    candidates: list[RetentionPriceEvidence] = []
    for price, mean, revenue, propensity in zip(
        prices,
        means,
        expected_revenue,
        probabilities,
        strict=False,
    ):
        allowed, stoploss_debug = should_apply_price(
            store,
            tenant_id=str(tenant_id),
            offer_arm=str(offer_arm),
            candidate_price_rub=int(price),
            base_price_rub=int(base),
            cfg=stoploss,
            now_ms=int(now_ms),
            context_key=context_key or None,
            window_hours=int(config["window_hours"]),
        )
        if not allowed and int(price) != int(base):
            continue
        debug = dict(common_debug)
        debug["candidate_price_rub"] = int(price)
        debug["stoploss"] = dict(stoploss_debug)
        candidates.append(
            RetentionPriceEvidence(
                price_rub=int(price),
                posterior_mean_conversion=float(mean),
                expected_revenue_rub=float(revenue),
                propensity=float(propensity),
                is_base=int(price) == int(base),
                stoploss_allowed=bool(allowed),
                debug=debug,
            )
        )
    if not candidates:
        return [_base_candidate(base_price_rub=base, note="stoploss_filtered", debug=common_debug)]
    if not any(candidate.is_base for candidate in candidates):
        candidates.append(_base_candidate(base_price_rub=base, note="base_restored", debug=common_debug))
    return candidates


def maybe_apply_rl_price(
    *,
    store,
    tenant_id: str,
    user_id: str,
    offer_arm: str,
    base_price_rub: int | None,
    now_ms: int,
    pricing_ctx: str,
    env_int,
    env_float,
    debug: dict[str, Any],
    policy: RetentionPricingFlowPolicy = DEFAULT_RETENTION_PRICING_FLOW_POLICY,
) -> int | None:
    """Compatibility shim: expose evidence but never choose outside DecisionCore."""

    del user_id
    candidates = build_price_candidates(
        store=store,
        tenant_id=tenant_id,
        offer_arm=offer_arm,
        base_price_rub=base_price_rub,
        now_ms=now_ms,
        pricing_ctx=pricing_ctx,
        env_int=env_int,
        env_float=env_float,
        policy=policy,
    )
    debug["pricing_candidates"] = [candidate.__dict__ for candidate in candidates]
    return int(base_price_rub) if base_price_rub is not None else None


def apply_stoploss(
    *,
    store,
    tenant_id: str,
    user_id: str,
    offer_arm: str,
    base_price_rub: int | None,
    current_price_rub: int | None,
    now_ms: int,
    pricing_ctx: str,
    env_int,
    env_float,
    debug: dict[str, Any],
    policy: RetentionPricingFlowPolicy = DEFAULT_RETENTION_PRICING_FLOW_POLICY,
) -> tuple[int | None, dict[str, Any]]:
    """Compatibility guard for an explicitly supplied price candidate."""

    del user_id
    if base_price_rub is None or current_price_rub is None:
        return current_price_rub, debug
    try:
        config = _stoploss_config(env_int=env_int, env_float=env_float, policy=policy)
        allowed, stoploss_debug = should_apply_price(
            store,
            tenant_id=str(tenant_id),
            offer_arm=str(offer_arm),
            candidate_price_rub=int(current_price_rub),
            base_price_rub=int(base_price_rub),
            cfg=config,
            now_ms=int(now_ms),
            context_key=str(pricing_ctx or "") or None,
            window_hours=int(
                env_int("PRICING_RL_WINDOW_HOURS", int(policy.rl_window_hours))
            ),
        )
        debug.setdefault("pricing_stoploss", {}).update(stoploss_debug)
        if not allowed:
            debug["pricing_stoploss"]["action"] = "fallback_to_base"
            return int(base_price_rub), debug
    except Exception:
        exception_throttled(
            log,
            key=f"pricing_stoploss|{tenant_id}",
            msg="pricing_stoploss: failed (ignored)",
        )
    return int(current_price_rub), debug
