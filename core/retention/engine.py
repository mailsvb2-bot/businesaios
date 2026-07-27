from __future__ import annotations

import logging
import time
from typing import Any

import core.retention.feature_extractor as fx_mod
from config.pricing_retention_policy import DEFAULT_RETENTION_ENGINE_POLICY, RetentionEnginePolicy
from core.retention.arms import (
    base_price_for_arm,
    build_candidates,
    filter_candidate_arms,
    score_arm_candidates_event_sourced,
)
from core.retention.engine_candidates import offer_candidates as _build_offer_candidates
from core.retention.engine_candidates import suppressed_evaluation as _suppressed_evaluation
from core.retention.engine_materialization import (
    find_candidate,
    materialize_candidate,
    materialized_offer,
    neutral_decision,
    sandbox_evaluation,
)
from core.retention.engine_models import RetentionDayDecision, RetentionDecision, RetentionEvaluation, RetentionOfferCandidate
from core.retention.engine_support import (
    build_sandbox_suppressed_decision,
    daily_offer_cap_reached,
    has_active_entitlement,
    is_outbound_overloaded,
    is_retention_allowed,
    parse_decide_offer_context,
)
from core.retention.ports import RetentionStore
from core.retention.pricing_flow import build_price_candidates
from core.retention.scoring import estimate_hazard, estimate_readiness, should_suppress_marketing
from core.tenancy.normalization import normalize_tenant_scope

logger = logging.getLogger(__name__)
__all__ = ["RetentionDayDecision", "RetentionDecision", "RetentionEngine", "RetentionEvaluation", "RetentionOfferCandidate", "evaluate_for_day", "materialize_candidate", "neutral_decision"]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _offer_candidates(**kwargs: Any) -> tuple[RetentionOfferCandidate, ...]:
    """Compatibility seam with explicit dependencies; it never selects a candidate."""
    return _build_offer_candidates(
        **kwargs,
        base_price_fn=base_price_for_arm,
        price_candidates_fn=build_price_candidates,
    )


def evaluate_for_day(
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
) -> RetentionEvaluation:
    """Build read-only retention evidence for the sovereign DecisionCore."""
    observed_at_ms = int(now_ms) if now_ms is not None else _now_ms()
    features = fx_mod.compute_features_for_day(store, tenant_id=tenant_id, user_id=user_id, day_key=day_key)
    hazard, readiness = float(estimate_hazard(features)), float(estimate_readiness(features))
    suppressed, reason = bool(should_suppress_marketing(hazard=hazard, readiness=readiness)), "suppressed"
    if not suppressed and has_active_entitlement(store, tenant_id=tenant_id, user_id=user_id, now_ms=observed_at_ms, entitlements=entitlements):
        suppressed, reason = True, "committed"
    if not suppressed and is_outbound_overloaded(outbound_telemetry, policy=policy):
        suppressed, reason = True, "outbound_overload"
    if not suppressed and daily_offer_cap_reached(store, tenant_id=tenant_id, user_id=user_id, day_key=day_key, now_ms=observed_at_ms, policy=policy):
        suppressed, reason = True, "daily_cap"
    debug: dict[str, Any] = {
        "features": dict(features), "hazard": hazard, "readiness": readiness,
        "suppressed": suppressed, "now_ms": observed_at_ms,
        "feature_snapshot_deferred_until_execution": True, "no_second_brain": True,
    }
    if suppressed:
        return _suppressed_evaluation(tenant_id=tenant_id, day_key=day_key, day_index=day_index, hazard=hazard, readiness=readiness, reason=reason, debug=debug)
    eligible, _ = build_candidates(day_index=int(day_index), prices=prices)
    eligible = filter_candidate_arms(store, tenant_id=tenant_id, user_id=user_id, candidates=eligible, now_ms=observed_at_ms, debug=debug, logger=logger)
    if not eligible:
        return RetentionEvaluation(str(tenant_id), str(day_key), int(day_index), hazard, readiness, False, "no_candidates", (), debug)
    arm_rows = score_arm_candidates_event_sourced(store, tenant_id=tenant_id, user_id=user_id, arms=eligible, now_ms=observed_at_ms)
    candidates = _offer_candidates(
        store=store, tenant_id=tenant_id, user_id=user_id, day_key=day_key,
        now_ms=observed_at_ms, readiness=readiness, hazard=hazard, arms=arm_rows,
        prices=prices, outbound_telemetry=outbound_telemetry,
    )
    debug.update(candidate_count=len(candidates), candidate_ids=[item.candidate_id for item in candidates])
    return RetentionEvaluation(
        str(tenant_id), str(day_key), int(day_index), hazard, readiness, False,
        "candidates_ready" if candidates else "no_price_candidates", candidates, debug,
    )


class RetentionEngine:
    """Read-only retention evidence provider for the sovereign DecisionCore."""

    def __init__(self, store: RetentionStore, tenant_id: str = "", policy: RetentionEnginePolicy = DEFAULT_RETENTION_ENGINE_POLICY):
        self._store = store
        self._tenant_id = normalize_tenant_scope(tenant_id, allow_unknown=True)
        self._policy = policy

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    def compute_evidence(
        self,
        *,
        user_id: str,
        now_ms: int | None = None,
        day_key: str = "day:today",
        day_index: int = 0,
        outbound_telemetry: dict | None = None,
        prices: dict | None = None,
        entitlements: dict | None = None,
    ) -> RetentionEvaluation:
        if not is_retention_allowed(tenant_id=self._tenant_id, user_id=str(user_id), fallback_allow=True):
            return sandbox_evaluation(build_sandbox_suppressed_decision(
                tenant_id=self._tenant_id, day_key=str(day_key), day_index=int(day_index), policy=self._policy,
            ))
        return evaluate_for_day(
            self._store, tenant_id=self._tenant_id, user_id=str(user_id), day_key=str(day_key),
            day_index=int(day_index), outbound_telemetry=outbound_telemetry, prices=prices,
            entitlements=entitlements, now_ms=now_ms, policy=self._policy,
        )

    def compute_decision(self, **kwargs: Any) -> RetentionDayDecision:
        """Compatibility telemetry surface; it never chooses a candidate."""
        return neutral_decision(self.compute_evidence(**kwargs))

    def decide_offer(self, *, tenant_id: str, user_id: str, context: dict) -> RetentionDecision | None:
        """Materialize only the candidate explicitly selected by DecisionCore."""
        requested_tenant = normalize_tenant_scope(tenant_id, allow_unknown=True)
        if self._tenant_id == "unknown_tenant" or requested_tenant != self._tenant_id:
            return None
        if not is_retention_allowed(tenant_id=self._tenant_id, user_id=str(user_id), fallback_allow=False):
            return None
        selected_candidate_id = str((context or {}).get("selected_candidate_id") or "").strip()
        if not selected_candidate_id:
            return None
        day_key, day_index, selected_at_ms = parse_decide_offer_context(context)
        evaluation = self.compute_evidence(
            user_id=str(user_id), day_key=day_key, day_index=day_index,
            now_ms=selected_at_ms if selected_at_ms is not None else _now_ms(),
            outbound_telemetry=context.get("outbound_telemetry"), prices=context.get("prices"),
            entitlements=context.get("entitlements"),
        )
        selected = materialize_candidate(evaluation, candidate_id=selected_candidate_id)
        return materialized_offer(selected, find_candidate(evaluation, candidate_id=selected_candidate_id))
