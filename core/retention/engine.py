from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any

import core.retention.feature_extractor as fx_mod
from config.pricing_retention_policy import DEFAULT_RETENTION_ENGINE_POLICY, RetentionEnginePolicy
from core.retention.ports import RetentionStore
from core.tenancy.normalization import normalize_tenant_scope

from .arms import (
    RetentionArmEvidence,
    base_price_for_arm,
    build_candidates,
    filter_candidate_arms,
    score_arm_candidates_event_sourced,
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
from .pricing_flow import RetentionPriceEvidence, build_price_candidates, pricing_context_key
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


@dataclass(frozen=True)
class RetentionOfferCandidate:
    candidate_id: str
    offer_arm: str
    offer_price_rub: int
    expected_profit_delta_minor: float
    ope_wis: float
    uplift: float
    risk_penalty: float
    propensity: float | None
    debug: dict[str, Any]


@dataclass(frozen=True)
class RetentionEvaluation:
    tenant_id: str
    day_key: str
    day_index: int
    hazard: float
    readiness: float
    suppressed: bool
    reason: str
    candidates: tuple[RetentionOfferCandidate, ...]
    debug: dict[str, Any]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _candidate_id(*, tenant_id: str, user_id: str, day_key: str, arm: str, price_rub: int) -> str:
    raw = "||".join((tenant_id, user_id, day_key, arm, str(int(price_rub))))
    return "ret_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _suppressed_evaluation(
    *,
    tenant_id: str,
    day_key: str,
    day_index: int,
    hazard: float,
    readiness: float,
    reason: str,
    debug: dict[str, Any],
) -> RetentionEvaluation:
    return RetentionEvaluation(
        tenant_id=str(tenant_id),
        day_key=str(day_key),
        day_index=int(day_index),
        hazard=float(hazard),
        readiness=float(readiness),
        suppressed=True,
        reason=str(reason),
        candidates=(),
        debug=dict(debug),
    )


def _offer_candidates(
    *,
    store: RetentionStore,
    tenant_id: str,
    user_id: str,
    day_key: str,
    now_ms: int,
    readiness: float,
    hazard: float,
    arms: list[RetentionArmEvidence],
    prices: dict | None,
    outbound_telemetry: dict | None,
) -> tuple[RetentionOfferCandidate, ...]:
    pricing_ctx = pricing_context_key(outbound_telemetry)
    candidates: list[RetentionOfferCandidate] = []
    safety_multiplier = max(0.0, 1.0 - float(hazard))
    for arm in arms:
        base_price_rub = base_price_for_arm(arm.arm, prices=prices)
        price_rows: list[RetentionPriceEvidence] = build_price_candidates(
            store=store,
            tenant_id=str(tenant_id),
            offer_arm=str(arm.arm),
            base_price_rub=base_price_rub,
            now_ms=int(now_ms),
            pricing_ctx=pricing_ctx,
            env_int=env_int_safe,
            env_float=env_float_safe,
        )
        for price in price_rows:
            expected_profit_minor = (
                float(price.expected_revenue_rub)
                * 100.0
                * float(arm.posterior_mean)
                * float(readiness)
                * safety_multiplier
            )
            if expected_profit_minor <= 0.0:
                expected_profit_minor = (
                    float(price.price_rub)
                    * 100.0
                    * float(arm.posterior_mean)
                    * float(readiness)
                    * safety_multiplier
                )
            debug = {
                "arm": arm.__dict__,
                "price": price.__dict__,
                "pricing_context": pricing_ctx,
            }
            candidates.append(
                RetentionOfferCandidate(
                    candidate_id=_candidate_id(
                        tenant_id=str(tenant_id),
                        user_id=str(user_id),
                        day_key=str(day_key),
                        arm=str(arm.arm),
                        price_rub=int(price.price_rub),
                    ),
                    offer_arm=str(arm.arm),
                    offer_price_rub=int(price.price_rub),
                    expected_profit_delta_minor=float(expected_profit_minor),
                    ope_wis=float(arm.posterior_mean),
                    uplift=float(readiness),
                    risk_penalty=float(hazard),
                    propensity=price.propensity,
                    debug=debug,
                )
            )
    return tuple(candidates)


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
    """Build retention evidence and admissible candidates without choosing.

    The function is read-only. Feature snapshots, bandit state, pricing-decision
    logs, cooldown marks, and outbound effects are not written before a signed
    DecisionCore envelope exists.
    """

    observed_at_ms = int(now_ms) if now_ms is not None else _now_ms()
    features = fx_mod.compute_features_for_day(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        day_key=day_key,
    )
    hazard = float(estimate_hazard(features))
    readiness = float(estimate_readiness(features))
    suppressed = bool(should_suppress_marketing(hazard=hazard, readiness=readiness))
    reason = "suppressed"
    if not suppressed and has_active_entitlement(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        now_ms=observed_at_ms,
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
        now_ms=observed_at_ms,
        policy=policy,
    ):
        suppressed, reason = True, "daily_cap"
    debug: dict[str, Any] = {
        "features": dict(features),
        "hazard": hazard,
        "readiness": readiness,
        "suppressed": suppressed,
        "now_ms": observed_at_ms,
        "feature_snapshot_deferred_until_execution": True,
        "no_second_brain": True,
    }
    if suppressed:
        return _suppressed_evaluation(
            tenant_id=tenant_id,
            day_key=day_key,
            day_index=day_index,
            hazard=hazard,
            readiness=readiness,
            reason=reason,
            debug=debug,
        )

    eligible, _ = build_candidates(day_index=int(day_index), prices=prices)
    eligible = filter_candidate_arms(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        candidates=eligible,
        now_ms=observed_at_ms,
        debug=debug,
        logger=logger,
    )
    if not eligible:
        return RetentionEvaluation(
            tenant_id=str(tenant_id),
            day_key=str(day_key),
            day_index=int(day_index),
            hazard=hazard,
            readiness=readiness,
            suppressed=False,
            reason="no_candidates",
            candidates=(),
            debug=debug,
        )

    arm_rows = score_arm_candidates_event_sourced(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        arms=eligible,
        now_ms=observed_at_ms,
    )
    candidates = _offer_candidates(
        store=store,
        tenant_id=tenant_id,
        user_id=user_id,
        day_key=day_key,
        now_ms=observed_at_ms,
        readiness=readiness,
        hazard=hazard,
        arms=arm_rows,
        prices=prices,
        outbound_telemetry=outbound_telemetry,
    )
    debug["candidate_count"] = len(candidates)
    debug["candidate_ids"] = [candidate.candidate_id for candidate in candidates]
    return RetentionEvaluation(
        tenant_id=str(tenant_id),
        day_key=str(day_key),
        day_index=int(day_index),
        hazard=hazard,
        readiness=readiness,
        suppressed=False,
        reason="candidates_ready" if candidates else "no_price_candidates",
        candidates=candidates,
        debug=debug,
    )


def neutral_decision(evaluation: RetentionEvaluation) -> RetentionDayDecision:
    debug = dict(evaluation.debug)
    debug["candidates"] = [candidate.__dict__ for candidate in evaluation.candidates]
    return RetentionDayDecision(
        tenant_id=evaluation.tenant_id,
        day_key=evaluation.day_key,
        day_index=evaluation.day_index,
        hazard=evaluation.hazard,
        readiness=evaluation.readiness,
        offer_arm="NONE",
        offer_price_rub=None,
        suppressed=evaluation.suppressed,
        reason=evaluation.reason,
        debug=debug,
    )


def materialize_candidate(
    evaluation: RetentionEvaluation,
    *,
    candidate_id: str,
) -> RetentionDayDecision:
    selected = next(
        (candidate for candidate in evaluation.candidates if candidate.candidate_id == str(candidate_id)),
        None,
    )
    if selected is None:
        raise KeyError("unknown_retention_candidate")
    debug = dict(evaluation.debug)
    debug["selected_candidate"] = selected.__dict__
    return RetentionDayDecision(
        tenant_id=evaluation.tenant_id,
        day_key=evaluation.day_key,
        day_index=evaluation.day_index,
        hazard=evaluation.hazard,
        readiness=evaluation.readiness,
        offer_arm=selected.offer_arm,
        offer_price_rub=selected.offer_price_rub,
        suppressed=False,
        reason="selected_by_decision_core",
        debug=debug,
    )


class RetentionEngine:
    """Read-only retention evidence provider for the sovereign DecisionCore."""

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
        if not is_retention_allowed(
            tenant_id=self._tenant_id,
            user_id=str(user_id),
            fallback_allow=True,
        ):
            sandbox = build_sandbox_suppressed_decision(
                tenant_id=self._tenant_id,
                day_key=str(day_key),
                day_index=int(day_index),
                policy=self._policy,
            )
            return RetentionEvaluation(
                tenant_id=str(sandbox["tenant_id"]),
                day_key=str(sandbox["day_key"]),
                day_index=int(sandbox["day_index"]),
                hazard=float(sandbox["hazard"]),
                readiness=float(sandbox["readiness"]),
                suppressed=True,
                reason=str(sandbox["reason"]),
                candidates=(),
                debug=dict(sandbox["debug"]),
            )
        return evaluate_for_day(
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

    def compute_decision(self, **kwargs: Any) -> RetentionDayDecision:
        """Compatibility surface returning evidence, never a hidden choice."""

        return neutral_decision(self.compute_evidence(**kwargs))

    def decide_offer(self, *, tenant_id: str, user_id: str, context: dict) -> RetentionDecision | None:
        """Materialize only an explicitly selected DecisionCore candidate."""

        if self._tenant_id == "unknown_tenant":
            return None
        requested_tenant = normalize_tenant_scope(tenant_id, allow_unknown=True)
        if requested_tenant != self._tenant_id or not is_retention_allowed(
            tenant_id=self._tenant_id,
            user_id=str(user_id),
            fallback_allow=False,
        ):
            return None
        selected_candidate_id = str((context or {}).get("selected_candidate_id") or "").strip()
        if not selected_candidate_id:
            return None
        day_key, day_index, now_ms = parse_decide_offer_context(context)
        evaluation = self.compute_evidence(
            user_id=str(user_id),
            day_key=day_key,
            day_index=day_index,
            now_ms=now_ms if now_ms is not None else _now_ms(),
            outbound_telemetry=context.get("outbound_telemetry"),
            prices=context.get("prices"),
            entitlements=context.get("entitlements"),
        )
        selected = materialize_candidate(evaluation, candidate_id=selected_candidate_id)
        candidate = next(
            candidate
            for candidate in evaluation.candidates
            if candidate.candidate_id == selected_candidate_id
        )
        return RetentionDecision(
            offer_id=f"offer:{selected.offer_arm}",
            variant_key=str(selected.offer_arm),
            price_rub=int(selected.offer_price_rub or 0),
            score=float(candidate.expected_profit_delta_minor),
        )
