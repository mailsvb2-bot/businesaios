from __future__ import annotations

import logging
from typing import Any

from config.retention_pricing_flow_policy import DEFAULT_RETENTION_PRICING_FLOW_POLICY, RetentionPricingFlowPolicy
from core.events.log import EventLog
from core.observability.throttled_logger import exception_throttled
from core.pricing.rl_picker import RLPricingConfig, choose_price_rub
from core.pricing.stop_loss import StopLossConfig, should_apply_price
from core.tenancy.scope import TenantScope

logger = logging.getLogger(__name__)


def pricing_context_key(telemetry: dict | None) -> str:
    t = telemetry or {}
    return str(t.get("traffic_source") or t.get("utm_source") or t.get("channel") or t.get("source") or "").strip()


def maybe_apply_rl_price(*, store, tenant_id: str, user_id: str, offer_arm: str, base_price_rub: int | None, now_ms: int, pricing_ctx: str, env_int, env_float, debug: dict[str, Any], policy: RetentionPricingFlowPolicy = DEFAULT_RETENTION_PRICING_FLOW_POLICY) -> int | None:
    price_rub = base_price_rub
    try:
        rl_enabled = bool(env_int("PRICING_RL_ENABLED", int(policy.rl_enabled_default)))
        if rl_enabled and base_price_rub is not None:
            cfg = RLPricingConfig(enabled=True, lookback_days=int(env_int("PRICING_RL_LOOKBACK_DAYS", int(policy.rl_lookback_days))), window_hours=int(env_int("PRICING_RL_WINDOW_HOURS", int(policy.rl_window_hours))), grid_radius_pct=float(env_float("PRICING_RL_GRID_RADIUS_PCT", float(policy.rl_grid_radius_pct))), grid_step_rub=int(env_int("PRICING_RL_GRID_STEP_RUB", int(policy.rl_grid_step_rub))), min_price_rub=int(env_int("PRICING_RL_MIN_PRICE_RUB", int(policy.rl_min_price_rub))), max_price_rub=int(env_int("PRICING_RL_MAX_PRICE_RUB", int(policy.rl_max_price_rub))))
            picked, dbg = choose_price_rub(store, tenant_id=str(tenant_id), offer_arm=str(offer_arm), base_price_rub=int(base_price_rub), cfg=cfg, now_ms=int(now_ms), context_key=pricing_ctx or None)
            price_rub = int(picked)
            debug.setdefault("pricing_rl", {}).update(dbg)
            try:
                from core.pricing.logging import emit_pricing_decision
                emit_pricing_decision(store, tenant_id=str(tenant_id), user_id=str(user_id), offer_arm=str(offer_arm), base_price_rub=int(base_price_rub), chosen_price_rub=int(price_rub), policy_id=str(dbg.get("policy_id") or "pricing_rl_v2"), propensity=(float(dbg.get("propensity")) if dbg.get("propensity") is not None else None), segment=(str(pricing_ctx) if pricing_ctx else None), candidates=(list(dbg.get("candidates") or []) if isinstance(dbg.get("candidates"), list) else None), probs=(dict(dbg.get("probs") or {}) if isinstance(dbg.get("probs"), dict) else None), timestamp_ms=int(now_ms), extra={"signal": str(dbg.get("signal") or ""), "method": str(dbg.get("method") or "")})
            except Exception:
                exception_throttled(logger, key=f"pricing_rl_emit|{tenant_id}", msg="pricing_rl: emit decision failed (ignored)")
    except Exception:
        exception_throttled(logger, key=f"pricing_rl|{tenant_id}", msg="pricing_rl: failed (fallback base)")
    return price_rub


def apply_stoploss(*, store, tenant_id: str, user_id: str, offer_arm: str, base_price_rub: int | None, current_price_rub: int | None, now_ms: int, pricing_ctx: str, env_int, env_float, debug: dict[str, Any], policy: RetentionPricingFlowPolicy = DEFAULT_RETENTION_PRICING_FLOW_POLICY) -> tuple[int | None, dict[str, Any]]:
    price_rub = current_price_rub
    try:
        sl_enabled = bool(env_int("PRICING_RL_STOPLOSS_ENABLED", int(policy.stoploss_enabled_default)))
        if sl_enabled and base_price_rub is not None and current_price_rub is not None:
            sl_cfg = StopLossConfig(enabled=True, lookback_hours=int(env_int("PRICING_RL_STOPLOSS_LOOKBACK_HOURS", int(policy.stoploss_lookback_hours))), min_trials=int(env_int("PRICING_RL_STOPLOSS_MIN_TRIALS", int(policy.stoploss_min_trials))), max_conv_drop_pct=float(env_float("PRICING_RL_STOPLOSS_MAX_CONV_DROP_PCT", float(policy.stoploss_max_conv_drop_pct))), max_rev_drop_pct=float(env_float("PRICING_RL_STOPLOSS_MAX_REV_DROP_PCT", float(policy.stoploss_max_rev_drop_pct))), cooldown_hours=int(env_int("PRICING_RL_STOPLOSS_COOLDOWN_HOURS", int(policy.stoploss_cooldown_hours))))
            ok, sl_dbg = should_apply_price(store, tenant_id=str(tenant_id), offer_arm=str(offer_arm), candidate_price_rub=int(current_price_rub), base_price_rub=int(base_price_rub), cfg=sl_cfg, now_ms=int(now_ms), context_key=pricing_ctx or None, window_hours=int(env_int("PRICING_RL_WINDOW_HOURS", int(policy.rl_window_hours))))
            debug.setdefault("pricing_stoploss", {}).update(sl_dbg)
            if not ok:
                price_rub = int(base_price_rub)
                debug["pricing_stoploss"]["action"] = "fallback_to_base"
                if str(sl_dbg.get("note") or "") not in {"cooldown_active"}:
                    try:
                        log = EventLog(store, tenant=TenantScope(str(tenant_id)))
                        payload = {"offer_arm": str(offer_arm), "candidate_price_rub": int(sl_dbg.get("candidate_price_rub") or current_price_rub or 0), "base_price_rub": int(sl_dbg.get("base_price_rub") or base_price_rub or 0), "reason": str(sl_dbg.get("note") or "")}
                        if pricing_ctx:
                            payload["segment"] = str(pricing_ctx)
                        log.emit(event_type="pricing_stoploss_triggered", source="pricing", user_id=str(user_id), payload=payload, timestamp_ms=int(now_ms))
                    except Exception:
                        exception_throttled(logger, key=f"pricing_stoploss_emit|{tenant_id}", msg="pricing_stoploss: emit trigger failed (ignored)")
    except Exception:
        exception_throttled(logger, key=f"pricing_stoploss|{tenant_id}", msg="pricing_stoploss: failed (ignored)")
    return price_rub, debug
