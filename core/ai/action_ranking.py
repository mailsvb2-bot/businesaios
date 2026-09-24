"""Canonical deterministic candidate-action ranking for DecisionCore."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from config.scoring_behavior_policy import DEFAULT_ACTION_RANKING_POLICY, ActionRankingPolicy

OBJECTIVE_DIMENSIONS = (
    "business_value",
    "revenue",
    "margin",
    "cash_flow",
    "risk",
    "customer_impact",
    "cost",
    "strategic_value",
)
_OBJECTIVE_PREFIX = "objective:"


@dataclass(frozen=True)
class RankedProposal:
    action: str
    payload: dict[str, Any]
    score: float
    reason: str
    ranking: dict[str, Any] = field(default_factory=dict)
    source_index: int = 0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _get_num(data: Mapping[str, Any], key: str) -> float:
    try:
        value = float(data.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


def _has_objective_projection(data: Mapping[str, Any]) -> bool:
    return any(str(key).startswith(_OBJECTIVE_PREFIX) for key in data)


def _objective_vector(data: Mapping[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for dimension in OBJECTIVE_DIMENSIONS:
        key = f"{_OBJECTIVE_PREFIX}{dimension}"
        if key not in data:
            raise ValueError("objective_projection_incomplete")
        raw = data.get(key)
        if isinstance(raw, bool):
            raise ValueError("objective_projection_invalid")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("objective_projection_invalid") from exc
        if not math.isfinite(value) or not -1.0 <= value <= 1.0:
            raise ValueError("objective_projection_invalid")
        values[dimension] = value
    return values


def _objective_score(
    values: Mapping[str, float],
    *,
    policy: ActionRankingPolicy,
) -> float:
    weights = {
        "business_value": policy.objective_business_value_weight,
        "revenue": policy.objective_revenue_weight,
        "margin": policy.objective_margin_weight,
        "cash_flow": policy.objective_cash_flow_weight,
        "risk": policy.objective_risk_weight,
        "customer_impact": policy.objective_customer_impact_weight,
        "cost": policy.objective_cost_weight,
        "strategic_value": policy.objective_strategic_value_weight,
    }
    total_weight = 0.0
    weighted_sum = 0.0
    for dimension in OBJECTIVE_DIMENSIONS:
        weight = float(weights[dimension])
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError("objective_weight_invalid")
        total_weight += weight
        weighted_sum += float(values[dimension]) * weight
    if total_weight <= 0.0:
        raise ValueError("objective_weight_invalid")
    return weighted_sum / total_weight


def _proposal_parts(proposal: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if isinstance(proposal, Mapping):
        action = str(proposal.get("action") or "")
        raw_payload = proposal.get("payload")
        payload = (
            _mapping(raw_payload)
            if isinstance(raw_payload, Mapping)
            else {str(k): v for k, v in proposal.items() if str(k) not in {"action", "ranking"}}
        )
        ranking = _mapping(proposal.get("ranking"))
        return action, payload, ranking
    return (
        str(getattr(proposal, "action", "")),
        _mapping(getattr(proposal, "payload", {})),
        _mapping(getattr(proposal, "ranking", {})),
    )


def score_proposal(
    *,
    action: str,
    payload: dict[str, Any],
    ranking: dict[str, Any] | None = None,
    policy: ActionRankingPolicy = DEFAULT_ACTION_RANKING_POLICY,
) -> tuple[float, str]:
    """Score decision candidates from metadata that is not signed as action input.

    Historical payload-embedded metadata remains a read-only compatibility
    fallback, but canonical callers use ``ProposedAction.ranking``.
    """

    metadata = dict(ranking or {}) or dict(payload or {})
    if _has_objective_projection(dict(ranking or {})):
        values = _objective_vector(dict(ranking or {}))
        return (
            float(_objective_score(values, policy=policy)),
            "multi_objective:" + "+".join(OBJECTIVE_DIMENSIONS),
        )
    expected_profit = _get_num(metadata, "expected_profit_delta_minor")
    ope_wis = _get_num(metadata, "ope_wis")
    uplift = _get_num(metadata, "uplift")
    risk = _get_num(metadata, "risk_penalty")
    score = (
        expected_profit * float(policy.expected_profit_weight)
        + ope_wis * float(policy.ope_wis_weight)
        + uplift * float(policy.uplift_weight)
        - risk * float(policy.risk_penalty_weight)
    )
    return float(score), "meta_profit+ope+uplift-risk"


def rank_proposals(
    proposals: Iterable[Any],
    *,
    policy: ActionRankingPolicy = DEFAULT_ACTION_RANKING_POLICY,
) -> list[RankedProposal]:
    parsed = [
        (index, *_proposal_parts(proposal))
        for index, proposal in enumerate(list(proposals or []))
    ]
    objective_mode = any(_has_objective_projection(ranking) for _, _, _, ranking in parsed)
    ranked: list[tuple[int, RankedProposal]] = []
    objective_errors = 0
    for index, action, payload, ranking in parsed:
        if objective_mode and not _has_objective_projection(ranking):
            continue
        try:
            if not action:
                continue
            score, reason = score_proposal(
                action=action,
                payload=payload,
                ranking=ranking,
                policy=policy,
            )
            ranked.append(
                (
                    index,
                    RankedProposal(
                        action=action,
                        payload=payload,
                        score=float(score),
                        reason=str(reason),
                        ranking=dict(ranking),
                        source_index=int(index),
                    ),
                )
            )
        except (TypeError, ValueError, OverflowError):
            if objective_mode:
                objective_errors += 1
            continue
    if objective_mode and not ranked:
        raise ValueError(
            "objective_projection_invalid"
            if objective_errors
            else "objective_projection_incomplete"
        )
    ranked.sort(key=lambda item: (-float(item[1].score), int(item[0])))
    return [item for _, item in ranked]
