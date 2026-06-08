from __future__ import annotations

from typing import Any

from runtime.platform.config.feature_flags import FeatureFlags


def load_pricing_suggestions(event_store: Any, *, tenant_id: str) -> dict[str, Any]:
    pricing_suggestions: dict[str, Any] = {}
    if not FeatureFlags.AUTOPRICING:
        return pricing_suggestions
    try:
        from core.plans import active_plans
        from core.pricing.autopricing import AutopricingConfig, suggest_prices_for_plans
        from core.pricing.rl_picker import RLPricingConfig
        from core.pricing.stop_loss import StopLossConfig

        cfg = AutopricingConfig(
            enabled=True,
            rl=RLPricingConfig(enabled=bool(FeatureFlags.AUTOPRICING_RL)),
            stop_loss=StopLossConfig(enabled=bool(FeatureFlags.AUTOPRICING_RL_STOPLOSS)),
        )
        pricing_suggestions = suggest_prices_for_plans(
            event_store,
            tenant_id=str(tenant_id),
            plans=list(active_plans())[:20],
            config=cfg,
            context_key="",
        )
    except Exception:
        pricing_suggestions = {}
    if pricing_suggestions:
        return pricing_suggestions
    try:
        from core.admin.ai_pricing import suggest_price_for_plan
        from core.plans import active_plans
        for p in list(active_plans())[:20]:
            try:
                pid = int(p.get("plan_id") or 0)
                base = int(p.get("price") or 0)
                if pid <= 0 or base <= 0:
                    continue
                sug = suggest_price_for_plan(
                    event_store,
                    tenant_id=str(tenant_id),
                    plan_id=pid,
                    base_price=base,
                    window_hours=24,
                    lookback_days=30,
                )
                pricing_suggestions[str(pid)] = int(sug.suggested_price)
            except Exception:
                continue
    except Exception:
        pricing_suggestions = {}
    return pricing_suggestions
