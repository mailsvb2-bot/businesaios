"""Canonical deterministic candidate-action ranking for DecisionCore."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from config.scoring_behavior_policy import DEFAULT_ACTION_RANKING_POLICY, ActionRankingPolicy


@dataclass(frozen=True)
class RankedProposal:
    action: str
    payload: dict[str, Any]
    score: float
    reason: str


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _get_num(data: Mapping[str, Any], key: str) -> float:
    try:
        value = float(data.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


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
    ranked: list[tuple[int, RankedProposal]] = []
    for index, proposal in enumerate(list(proposals or [])):
        try:
            action, payload, ranking = _proposal_parts(proposal)
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
                    ),
                )
            )
        except (TypeError, ValueError, OverflowError):
            continue
    ranked.sort(key=lambda item: (-float(item[1].score), int(item[0])))
    return [item for _, item in ranked]
