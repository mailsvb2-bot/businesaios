from __future__ import annotations

"""Tiny candidate action ranking.

DecisionCore can optionally select from multiple proposals.
This module is intentionally dumb and deterministic.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from config.scoring_behavior_policy import DEFAULT_ACTION_RANKING_POLICY, ActionRankingPolicy


@dataclass(frozen=True)
class RankedProposal:
    action: str
    payload: dict[str, Any]
    score: float
    reason: str


def _get_num(d: dict[str, Any], key: str) -> float:
    try:
        return float(d.get(key))
    except Exception:
        return 0.0


def score_proposal(
    *,
    action: str,
    payload: dict[str, Any],
    policy: ActionRankingPolicy = DEFAULT_ACTION_RANKING_POLICY,
) -> tuple[float, str]:
    """Prefer proposals that carry explicit evaluation metadata.

    Supported optional keys in payload:
      - expected_profit_delta_minor
      - ope_wis
      - uplift
      - risk_penalty
    """

    p = dict(payload or {})
    exp = _get_num(p, "expected_profit_delta_minor")
    wis = _get_num(p, "ope_wis")
    uplift = _get_num(p, "uplift")
    risk = _get_num(p, "risk_penalty")

    score = (
        (exp * float(policy.expected_profit_weight))
        + (wis * float(policy.ope_wis_weight))
        + (uplift * float(policy.uplift_weight))
        - (risk * float(policy.risk_penalty_weight))
    )
    return float(score), "meta_profit+ope+uplift-risk"


def rank_proposals(
    proposals: Iterable[Any],
    *,
    policy: ActionRankingPolicy = DEFAULT_ACTION_RANKING_POLICY,
) -> list[RankedProposal]:
    ranked: list[RankedProposal] = []
    for pr in list(proposals or []):
        try:
            a = str(getattr(pr, "action", ""))
            pl = dict(getattr(pr, "payload", {}) or {})
            sc, rsn = score_proposal(action=a, payload=pl, policy=policy)
            ranked.append(RankedProposal(action=a, payload=pl, score=float(sc), reason=str(rsn)))
        except Exception:
            continue
    ranked.sort(key=lambda x: float(x.score), reverse=True)
    return ranked
