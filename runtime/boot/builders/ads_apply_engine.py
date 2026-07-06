from __future__ import annotations

import logging
from typing import Any

from runtime.platform.config.env_flags import env_bool, env_float, env_int

CANON_BOOT_WIRING_ONLY = True

"""AdsApplyEngine constructor for the boot pipeline.

Responsibility: wire AdsApplyEngine from env config and an already-built
AdsRuntime. Returns None (gracefully degraded) if anything is unavailable.

Single public function: build_ads_apply_engine()
"""



logger = logging.getLogger(__name__)


def build_ads_apply_engine(ads_runtime: Any) -> Any | None:
    """Construct AdsApplyEngine or return None on failure."""
    try:
        from runtime.ads import (
            AdsApplyEngine,
            AdsApplyEnv,
            AdsApplyLimits,
            AdsKillSwitch,
            AdsRateLimiter,
            MemoryIdempotencyStore,
        )
        from runtime.boot.ads_apply_provider import AdsGatewayApplyPort
        from runtime.governance import FeedbackLoopGuard, ProfitMetricsService

        env_enabled = env_bool("ADS_APPLY_ENABLED", False)
        max_budget_minor = env_int("ADS_APPLY_MAX_DAILY_BUDGET_MINOR", 0)
        max_changes = env_int("ADS_APPLY_MAX_CHANGES_PER_DAY", 0)
        rate_rps = env_float("ADS_APPLY_RATE_LIMIT_RPS", 2.0)
        rate_burst = env_int("ADS_APPLY_RATE_LIMIT_BURST", 5)

        sink = getattr(ads_runtime.write_gateway, "_sink", None)
        event_store = getattr(sink, "event_store", None)
        feedback_guard = None
        if event_store is not None:
            profit_metrics = ProfitMetricsService(event_store=event_store)
            feedback_guard = FeedbackLoopGuard(
                metrics=profit_metrics,
                lookback_days=env_int("ADS_FEEDBACK_LOOKBACK_DAYS", 3),
                max_budget_increase_pct=env_int("ADS_FEEDBACK_MAX_BUDGET_INCREASE_PCT", 10),
                require_positive_profit=env_bool("ADS_FEEDBACK_REQUIRE_POSITIVE_PROFIT", True),
            )

        return AdsApplyEngine(
            apply_port=AdsGatewayApplyPort(ads_runtime.write_gateway),
            kill_switch=AdsKillSwitch(),
            rate_limiter=AdsRateLimiter(rate=rate_rps, burst=rate_burst),
            idempotency=MemoryIdempotencyStore(),
            env=AdsApplyEnv(
                hard_env_enabled=env_enabled,
                limits=AdsApplyLimits(
                    max_daily_budget_minor=max_budget_minor,
                    max_changes_per_day=max_changes,
                ),
            ),
            feedback_guard=feedback_guard,
        )
    except Exception as exc:
        logger.debug("AdsApplyEngine unavailable (graceful degradation): %r", exc)
        return None
