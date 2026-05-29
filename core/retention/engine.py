from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from config.pricing_retention_policy import (
    DEFAULT_RETENTION_ENGINE_POLICY,
    RetentionEnginePolicy,
)
from core.retention.config.pricing_ladder import WINDOWS
from core.retention.ports import RetentionStore
from core.tenancy.normalization import normalize_tenant_scope

from . import feature_extractor as fx_mod
from .arms import (
    base_price_for_arm,
    build_candidates,
    choose_arm_event_sourced,
    filter_candidate_arms,
)
from .engine_support import (
    build_sandbox_suppressed_decision,
    daily_offer_cap_reached,
    env_float_safe,
    env_int_safe,
    has_active_entitlement,
    is_outbound_overloaded,
    is_retention_allowed,
    parse_decide_offer_context,
)
from .pricing_flow import apply_stoploss, maybe_apply_rl_price, pricing_context_key
from .scoring import estimate_hazard, estimate_readiness, should_suppress_marketing

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionDecision:
    offer_id: str
    variant_key: str
    price_rub: int
    score: float = DEFAULT_RETENTION_ENGINE_POLICY.decision_score_floor


@dataclass(frozen=True)
class RetentionDayDecision:
    tenant_id: str
    day_key: str
    day_index: int
    hazard: float
    readiness: float
    offer_arm: str
    offer_price_rub: int | None
    suppressed: bool
    reason: str
    debug: dict[str, Any]


def _now_ms() -> int:
    return int(time.time() * 1000)


def decide_for_day(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    day_key: str,
    day_index: int,
    now_ms: int | None = None,
    outbound_telemetry: dict | None = None,
    prices: dict | None = None,
    entitlements: dict | None = None,
    policy: RetentionEnginePolicy = DEFAULT_RETENTION_ENGINE_POLICY,
) -> RetentionDayDecision:
    now_ms = int(now_ms) if now_ms is not None else _now_ms()
    features = fx_mod.compute_features_for_day(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        day_key=day_key,
    )
    fx_mod.store_features_for_day(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        day_key=day_key,
        features=features,
        now_ms=now_ms,
    )
    hazard = estimate_hazard(features)
    readiness = estimate_readiness(features)
    suppressed = should_suppress_marketing(hazard=hazard, readiness=readiness)
    reason = "suppressed"
    if not suppressed and has_active_entitlement(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        now_ms=now_ms,
        entitlements=entitlements,
    ):
        suppressed, reason = True, "committed"
    if not suppressed and is_outbound_overloaded(outbound_telemetry, policy=policy):
        suppressed, reason = True, "outbound_overload"
    if not suppressed and daily_offer_cap_reached(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        day_key=day_key,
        now_ms=now_ms,
        policy=policy,
    ):
        suppressed, reason = True, "daily_cap"
    debug: dict[str, Any] = {
        "features": dict(features),
        "hazard": hazard,
        "readiness": readiness,
        "suppressed": suppressed,
        "now_ms": now_ms,
    }
    if suppressed:
        return RetentionDayDecision(
            tenant_id=tenant_id,
            day_key=day_key,
            day_index=int(day_index),
            hazard=hazard,
            readiness=readiness,
            offer_arm="NONE",
            offer_price_rub=None,
            suppressed=True,
            reason=reason,
            debug=debug,
        )
    candidates, _ = build_candidates(day_index=int(day_index), prices=prices)
    candidates = filter_candidate_arms(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        candidates=candidates,
        now_ms=now_ms,
        debug=debug,
        logger=logger,
    )
    if not candidates:
        return RetentionDayDecision(
            tenant_id=tenant_id,
            day_key=day_key,
            day_index=int(day_index),
            hazard=hazard,
            readiness=readiness,
            offer_arm="NONE",
            offer_price_rub=None,
            suppressed=False,
            reason="no_candidates",
            debug=debug,
        )
    offer_arm = choose_arm_event_sourced(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        arms=candidates,
        now_ms=now_ms,
    )
    base_price_rub = base_price_for_arm(str(offer_arm), prices=prices)
    pricing_ctx = pricing_context_key(outbound_telemetry)
    price_rub = maybe_apply_rl_price(
        store=store,
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        offer_arm=str(offer_arm),
        base_price_rub=base_price_rub,
        now_ms=int(now_ms),
        pricing_ctx=pricing_ctx,
        env_int=env_int_safe,
        env_float=env_float_safe,
        debug=debug,
    )
    price_rub, debug = apply_stoploss(
        store=store,
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        offer_arm=str(offer_arm),
        base_price_rub=base_price_rub,
        current_price_rub=price_rub,
        now_ms=int(now_ms),
        pricing_ctx=pricing_ctx,
        env_int=env_int_safe,
        env_float=env_float_safe,
        debug=debug,
    )
    return RetentionDayDecision(
        tenant_id=tenant_id,
        day_key=day_key,
        day_index=int(day_index),
        hazard=hazard,
        readiness=readiness,
        offer_arm=str(offer_arm),
        offer_price_rub=int(price_rub) if price_rub is not None else None,
        suppressed=False,
        reason="chosen",
        debug=debug,
    )


class RetentionEngine:
    """Single canonical retention engine."""

    def __init__(
        self,
        store: RetentionStore,
        tenant_id: str = "",
        policy: RetentionEnginePolicy = DEFAULT_RETENTION_ENGINE_POLICY,
    ):
        self._store = store
        self._tenant_id = normalize_tenant_scope(tenant_id, allow_unknown=True)
        self._policy = policy

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    def compute_decision(
        self,
        *,
        user_id: str,
        now_ms: int | None = None,
        day_key: str = "day:today",
        day_index: int = 0,
        outbound_telemetry: dict | None = None,
        prices: dict | None = None,
        entitlements: dict | None = None,
    ) -> RetentionDayDecision:
        if not is_retention_allowed(
            tenant_id=self._tenant_id,
            user_id=str(user_id),
            fallback_allow=True,
        ):
            return RetentionDayDecision(
                **build_sandbox_suppressed_decision(
                    tenant_id=self._tenant_id,
                    day_key=str(day_key),
                    day_index=int(day_index),
                    policy=self._policy,
                )
            )
        return decide_for_day(
            self._store,
            tenant_id=self._tenant_id,
            user_id=str(user_id),
            day_key=str(day_key),
            day_index=int(day_index),
            outbound_telemetry=outbound_telemetry,
            prices=prices,
            entitlements=entitlements,
            now_ms=now_ms,
            policy=self._policy,
        )

    def decide_offer(
        self,
        *,
        tenant_id: str,
        user_id: str,
        context: dict,
    ) -> RetentionDecision | None:
        if self._tenant_id == "unknown_tenant":
            return None
        requested_tenant = normalize_tenant_scope(tenant_id, allow_unknown=True)
        if requested_tenant != self._tenant_id:
            return None
        if not is_retention_allowed(
            tenant_id=self._tenant_id,
            user_id=str(user_id),
            fallback_allow=False,
        ):
            return None
        day_key, day_index, now_ms = parse_decide_offer_context(context)
        decision = decide_for_day(
            self._store,
            tenant_id=self._tenant_id,
            user_id=str(user_id),
            day_key=day_key,
            day_index=day_index,
            now_ms=now_ms if now_ms is not None else _now_ms(),
            outbound_telemetry=context.get("outbound_telemetry"),
            prices=context.get("prices"),
            entitlements=context.get("entitlements"),
            policy=self._policy,
        )
        if decision.suppressed or decision.offer_arm == "NONE" or decision.offer_price_rub is None:
            return None
        return RetentionDecision(
            offer_id=f"offer:{decision.offer_arm}",
            variant_key=str(decision.offer_arm),
            price_rub=int(decision.offer_price_rub),
            score=float(decision.readiness)
            * (float(self._policy.score_complement_base) - float(decision.hazard)),
        )
