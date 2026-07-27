"""Pure helpers for proposal generation and candidate ranking."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from core.ai.action_ranking import rank_proposals


def _allow_rank_fallback(policy: Any) -> bool:
    return bool(getattr(policy, "allow_rank_fallback", False))


def _fallback_proposal(*, policy: Any, state: Any, trace: Any, reason: str) -> Any:
    trace.try_add_step(
        name="rank_candidates_fallback",
        input={},
        output={"reason": str(reason), "fallback_allowed": _allow_rank_fallback(policy)},
    )
    if not _allow_rank_fallback(policy):
        raise RuntimeError(f"DECISION_POLICY_STAGE_FAILED:{reason}")
    return policy.propose(state)


def _materialize_ranked(*, prototype: Any, action: str, payload: dict[str, Any]) -> Any:
    if isinstance(prototype, dict):
        return SimpleNamespace(action=str(action), payload=dict(payload))
    try:
        return type(prototype)(action=str(action), payload=dict(payload))
    except TypeError:
        return SimpleNamespace(action=str(action), payload=dict(payload))


def propose_action(*, policy: Any, state: Any, trace: Any) -> Any:
    if not hasattr(policy, "propose_many"):
        return policy.propose(state)
    try:
        candidates = list(policy.propose_many(state) or [])
    except Exception as exc:
        return _fallback_proposal(
            policy=policy,
            state=state,
            trace=trace,
            reason=f"propose_many_error:{exc.__class__.__name__}",
        )
    if not candidates:
        return _fallback_proposal(
            policy=policy,
            state=state,
            trace=trace,
            reason="empty_candidates",
        )
    ranked = rank_proposals(candidates)
    if not ranked:
        return _fallback_proposal(
            policy=policy,
            state=state,
            trace=trace,
            reason="ranked_candidates_empty",
        )
    selected = ranked[0]
    output = _materialize_ranked(
        prototype=candidates[0],
        action=selected.action,
        payload=selected.payload,
    )
    trace.try_add_step(
        name="rank_candidates",
        input={"n": int(len(ranked))},
        output={
            "chosen_action": str(selected.action),
            "score": float(selected.score),
            "reason": str(selected.reason),
        },
    )
    return output
