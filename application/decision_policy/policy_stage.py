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


def _materialize_ranked(
    *,
    prototype: Any,
    action: str,
    payload: dict[str, Any],
    ranking: dict[str, Any],
    decision_context: dict[str, Any],
) -> Any:
    if isinstance(prototype, dict):
        return SimpleNamespace(action=str(action), payload=dict(payload), ranking=dict(ranking))
    try:
        output = type(prototype)(
            action=str(action),
            payload=dict(payload),
            ranking=dict(ranking),
        )
    except TypeError:
        try:
            output = type(prototype)(action=str(action), payload=dict(payload))
        except TypeError:
            return SimpleNamespace(
                action=str(action),
                payload=dict(payload),
                ranking=dict(ranking),
                _decision_context=dict(decision_context),
            )
        try:
            setattr(output, "ranking", dict(ranking))
        except (AttributeError, TypeError):
            return SimpleNamespace(
                action=str(action),
                payload=dict(payload),
                ranking=dict(ranking),
                _decision_context=dict(decision_context),
            )
    try:
        object.__setattr__(output, "_decision_context", dict(decision_context))
    except (AttributeError, TypeError):
        pass
    return output


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
    try:
        ranked = rank_proposals(candidates)
    except ValueError as exc:
        raise RuntimeError(f"DECISION_POLICY_STAGE_FAILED:{exc}") from exc
    if not ranked:
        return _fallback_proposal(
            policy=policy,
            state=state,
            trace=trace,
            reason="ranked_candidates_empty",
        )
    selected = ranked[0]
    decision_alternatives = [
        {
            "option_id": str(item.action),
            "score": float(item.score),
            "reason": str(item.reason),
        }
        for item in ranked
    ]
    decision_context = {
        "alternatives": decision_alternatives,
        "selection": {
            "option_id": str(selected.action),
            "score": float(selected.score),
            "reason": str(selected.reason),
        },
    }
    output = _materialize_ranked(
        prototype=candidates[selected.source_index],
        action=selected.action,
        payload=selected.payload,
        ranking=dict(selected.ranking),
        decision_context=decision_context,
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
