"""Pricing stop-loss guard (event-sourced).

Canonical facade over focused stop-loss helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from config.pricing_retention_policy import (
    DEFAULT_PRICING_STOP_LOSS_POLICY,
    PricingStopLossPolicy,
)
from core.pricing.stop_loss_parts.config import StopLossConfig
from core.pricing.stop_loss_parts.cooldown import cooldown_state
from core.pricing.stop_loss_parts.cooldown import now_ms as current_time_ms
from core.pricing.stop_loss_parts.metrics import (
    collect_payments_index,
    collect_trials,
    conv_and_rev_per_trial,
    stats_trials_successes,
)

def should_apply_price(
    event_store: Any,
    *,
    tenant_id: str,
    offer_arm: str,
    candidate_price_rub: int,
    base_price_rub: int,
    cfg: StopLossConfig,
    now_ms: int | None = None,
    context_key: str | None = None,
    window_hours: int = 24,
    policy: PricingStopLossPolicy = DEFAULT_PRICING_STOP_LOSS_POLICY,
) -> tuple[bool, dict[str, Any]]:
    cand = int(candidate_price_rub)
    base = int(base_price_rub)
    debug: dict[str, Any] = {
        "enabled": bool(cfg.enabled),
        "method": "pricing_stop_loss_event_sourced_v1",
        "candidate_price_rub": int(cand),
        "base_price_rub": int(base),
    }
    if not cfg.enabled:
        debug["note"] = "disabled"
        return True, debug
    if cand == base:
        debug["note"] = "same_as_base"
        return True, debug

    current_ms = int(now_ms if now_ms is not None else current_time_ms())
    ctx = str(context_key or "").strip()
    cd = cooldown_state(
        event_store,
        tenant_id=str(tenant_id),
        offer_arm=str(offer_arm),
        context_key=ctx,
        now_ms=int(current_ms),
        base_cooldown_hours=int(cfg.cooldown_hours),
        max_cooldown_hours=int(cfg.cooldown_max_hours),
        backoff_lookback_hours=int(cfg.cooldown_backoff_lookback_hours),
        decay_enabled=bool(cfg.cooldown_decay_enabled),
    )
    debug.update(
        {
            "cooldown_base_hours": int(cfg.cooldown_hours),
            "cooldown_max_hours": int(cfg.cooldown_max_hours),
            "cooldown_backoff_lookback_hours": int(cfg.cooldown_backoff_lookback_hours),
            "cooldown_effective_hours": int(cd.get("effective_cooldown_hours") or 0),
            "cooldown_recent_triggers": int(cd.get("recent_triggers") or 0),
            "cooldown_burst_count": int(cd.get("burst_count") or 0),
            "cooldown_decay_enabled": bool(cd.get("decay_enabled")),
        }
    )
    if cd.get("burst_evidence"):
        debug["cooldown_burst_evidence"] = cd.get("burst_evidence")
    if cd.get("last_trigger_ms") is not None:
        debug["cooldown_last_trigger_ms"] = int(cd.get("last_trigger_ms") or 0)
    if bool(cd.get("active")):
        debug["note"] = "cooldown_active"
        if ctx:
            debug["context_key"] = ctx
        return False, debug

    start_ms = int(current_ms) - int(max(1, cfg.lookback_hours)) * 3600 * 1000
    end_ms = int(current_ms)
    if ctx:
        debug["context_key"] = ctx

    trials = collect_trials(
        event_store,
        tenant_id=str(tenant_id),
        offer_arm=str(offer_arm),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        context_key=ctx,
    )
    debug["trials"] = int(len(trials))
    if not trials:
        debug["note"] = "no_trials"
        return True, debug

    payments = collect_payments_index(
        event_store,
        tenant_id=str(tenant_id),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
    )
    stats = stats_trials_successes(
        trials,
        payments,
        window_ms=int(max(1, window_hours)) * 3600 * 1000,
    )
    debug["observed_prices"] = int(len(stats))
    if not stats:
        debug["note"] = "no_stats"
        return True, debug

    observed = sorted(stats.keys())
    base_obs = min(observed, key=lambda x: abs(int(x) - int(base)))
    cand_obs = cand if cand in stats else min(observed, key=lambda x: abs(int(x) - int(cand)))
    debug["baseline_observed_price"] = int(base_obs)
    debug["candidate_observed_price"] = int(cand_obs)

    base_trials, base_succ = stats.get(int(base_obs), (0, 0))
    cand_trials, cand_succ = stats.get(int(cand_obs), (0, 0))
    debug["baseline_trials"] = int(base_trials)
    debug["candidate_trials"] = int(cand_trials)
    if base_trials < int(cfg.min_trials) or cand_trials < int(cfg.min_trials):
        debug["note"] = "insufficient_trials"
        return True, debug

    base_conv, base_rpt = conv_and_rev_per_trial(
        int(base_trials),
        int(base_succ),
        int(base_obs),
    )
    cand_conv, cand_rpt = conv_and_rev_per_trial(
        int(cand_trials),
        int(cand_succ),
        int(cand_obs),
    )
    debug.update(
        {
            "baseline_conv": float(base_conv),
            "candidate_conv": float(cand_conv),
            "baseline_rev_per_trial": float(base_rpt),
            "candidate_rev_per_trial": float(cand_rpt),
        }
    )
    unit_ratio = float(policy.unit_ratio)
    conv_floor = float(base_conv) * (unit_ratio - float(cfg.max_conv_drop_pct))
    rpt_floor = float(base_rpt) * (unit_ratio - float(cfg.max_rev_drop_pct))
    debug["conv_floor"] = float(conv_floor)
    debug["rev_per_trial_floor"] = float(rpt_floor)
    if cand_conv < conv_floor:
        debug["note"] = "blocked_conv_drop"
        return False, debug
    if cand_rpt < rpt_floor:
        debug["note"] = "blocked_rev_drop"
        return False, debug
    debug["note"] = "ok"
    return True, debug


@dataclass(frozen=True)
class StopLossDecision:
    allowed: bool
    reason: str
    details: dict[str, Any]


@dataclass(frozen=True)
class StopLossWindow:
    hours: int = 24


@dataclass(frozen=True)
class StopLossPolicy:
    config: StopLossConfig
    window: StopLossWindow = StopLossWindow()
    policy: PricingStopLossPolicy = DEFAULT_PRICING_STOP_LOSS_POLICY

    def evaluate(
        self,
        event_store: Any,
        *,
        tenant_id: str,
        offer_arm: str,
        candidate_price_rub: int,
        base_price_rub: int,
        now_ms: int | None = None,
        context_key: str | None = None,
    ) -> StopLossDecision:
        allowed, details = should_apply_price(
            event_store,
            tenant_id=tenant_id,
            offer_arm=offer_arm,
            candidate_price_rub=candidate_price_rub,
            base_price_rub=base_price_rub,
            cfg=self.config,
            now_ms=now_ms,
            context_key=context_key,
            window_hours=int(self.window.hours),
            policy=self.policy,
        )
        return StopLossDecision(
            allowed=bool(allowed),
            reason=str(details.get("note") or "unknown"),
            details=details,
        )


__all__ = [
    "StopLossConfig",
    "StopLossDecision",
    "StopLossPolicy",
    "StopLossWindow",
    "should_apply_price",
]
