from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from core.retention.arms import RetentionArmEvidence
from core.retention.engine_models import RetentionEvaluation, RetentionOfferCandidate
from core.retention.engine_support import env_float_safe, env_int_safe
from core.retention.ports import RetentionStore
from core.retention.pricing_flow import RetentionPriceEvidence, pricing_context_key

BasePriceFn = Callable[..., int | None]
PriceCandidatesFn = Callable[..., list[RetentionPriceEvidence]]


def _candidate_id(*, tenant_id: str, user_id: str, day_key: str, arm: str, price_rub: int) -> str:
    raw = "||".join((tenant_id, user_id, day_key, arm, str(int(price_rub))))
    return "ret_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def suppressed_evaluation(
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


def offer_candidates(
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
    base_price_fn: BasePriceFn,
    price_candidates_fn: PriceCandidatesFn,
) -> tuple[RetentionOfferCandidate, ...]:
    """Convert arm and price evidence into unselected DecisionCore candidates."""

    pricing_ctx = pricing_context_key(outbound_telemetry)
    candidates: list[RetentionOfferCandidate] = []
    safety_multiplier = max(0.0, 1.0 - float(hazard))
    for arm in arms:
        base_price_rub = base_price_fn(arm.arm, prices=prices)
        price_rows = price_candidates_fn(
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
                    debug={"arm": arm.__dict__, "price": price.__dict__, "pricing_context": pricing_ctx},
                )
            )
    return tuple(candidates)
