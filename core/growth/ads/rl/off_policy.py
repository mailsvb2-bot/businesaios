from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .experience_store import RLStep


@dataclass(frozen=True)
class OpeEstimate:
    estimator: str
    value: float
    n: int
    notes: str = ""


def ips_for_deterministic_target(*, steps: Iterable[RLStep], target_action_key: str) -> OpeEstimate:
    """Inverse Propensity Scoring for a deterministic target policy.

    Requires each step.meta['propensity'] in (0,1].
    """
    num = 0.0
    n = 0
    for s in steps:
        if s.reward is None:
            continue
        p = _propensity(s)
        if p <= 0:
            continue
        n += 1
        if str(s.action_key) == str(target_action_key):
            num += float(s.reward) / float(p)
    return OpeEstimate("ips", float(num) / max(1, n), n, "")


def snips_for_deterministic_target(*, steps: Iterable[RLStep], target_action_key: str) -> OpeEstimate:
    """Self-normalized IPS."""
    num = 0.0
    den = 0.0
    n = 0
    for s in steps:
        if s.reward is None:
            continue
        p = _propensity(s)
        if p <= 0:
            continue
        n += 1
        if str(s.action_key) == str(target_action_key):
            w = 1.0 / float(p)
            num += w * float(s.reward)
            den += w
    v = (num / den) if den > 0 else 0.0
    return OpeEstimate("snips", float(v), n, "")


def doubly_robust_for_deterministic_target(*, steps: Iterable[RLStep], target_action_key: str, qhat: float) -> OpeEstimate:
    """Very small Doubly Robust estimator (scalar baseline qhat).

    This is intentionally minimal; full DR requires per-action reward model.
    """
    num = 0.0
    n = 0
    for s in steps:
        if s.reward is None:
            continue
        p = _propensity(s)
        if p <= 0:
            continue
        n += 1
        r = float(s.reward)
        if str(s.action_key) == str(target_action_key):
            num += qhat + (r - qhat) / float(p)
        else:
            num += qhat
    return OpeEstimate("dr", float(num) / max(1, n), n, f"qhat={float(qhat):.6g}")


def _propensity(step: RLStep) -> float:
    try:
        meta = step.meta or {}
        p = meta.get("propensity")
        return float(p)
    except Exception:
        return 0.0


from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class OffPolicyActionScore:
    action_key: str
    score_name: str
    score_value: float
    explanation: str


def score_target_actions(
    *,
    steps: Iterable[RLStep],
    target_action_keys: Sequence[str],
) -> tuple[OffPolicyActionScore, ...]:
    """Advisory helper: compute comparable off-policy scores for candidate actions.

    This function scores actions; it does NOT choose a winner.
    """
    out: list[OffPolicyActionScore] = []
    for action_key in target_action_keys:
        estimate = snips_for_deterministic_target(
            steps=steps,
            target_action_key=str(action_key),
        )
        out.append(
            OffPolicyActionScore(
                action_key=str(action_key),
                score_name="snips_value",
                score_value=float(estimate.value),
                explanation="off_policy_score_only",
            )
        )
    return tuple(out)


from application.decisioning.candidate_space import build_candidate_space

def advisory_candidate_scores(*, steps, target_action_keys):
    scores = score_target_actions(steps=steps, target_action_keys=target_action_keys)
    return build_candidate_space(
        candidates=[s.action_key for s in scores],
        scores=[s.score_value for s in scores],
        source="rl_off_policy",
    )
