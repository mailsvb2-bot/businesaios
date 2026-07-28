from __future__ import annotations

from core.retention.engine_models import (
    RetentionDayDecision,
    RetentionDecision,
    RetentionEvaluation,
    RetentionOfferCandidate,
)


def sandbox_evaluation(sandbox: dict) -> RetentionEvaluation:
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


def find_candidate(evaluation: RetentionEvaluation, *, candidate_id: str) -> RetentionOfferCandidate:
    selected = next((item for item in evaluation.candidates if item.candidate_id == str(candidate_id)), None)
    if selected is None:
        raise KeyError("unknown_retention_candidate")
    return selected


def materialize_candidate(evaluation: RetentionEvaluation, *, candidate_id: str) -> RetentionDayDecision:
    selected = find_candidate(evaluation, candidate_id=candidate_id)
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


def materialized_offer(selected: RetentionDayDecision, candidate: RetentionOfferCandidate) -> RetentionDecision:
    return RetentionDecision(
        offer_id=f"offer:{selected.offer_arm}",
        variant_key=str(selected.offer_arm),
        price_rub=int(selected.offer_price_rub or 0),
        score=float(candidate.expected_profit_delta_minor),
    )
