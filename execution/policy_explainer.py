from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.action_capability_matrix import get_action_capability
from execution.autonomy_tiers import AutonomyDecision, evaluate_autonomy_tier


CANON_HEADLESS_POLICY_EXPLAINER = True


@dataclass(frozen=True)
class PolicyExplanation:
    policy_id: str
    summary: str
    factors: tuple[str, ...]


@dataclass(frozen=True)
class PolicyExplainer:
    """Explain an already-issued policy decision without changing it."""

    def explain(self, *, state: Any, envelope: Any) -> PolicyExplanation:
        policy_id = str(getattr(envelope.decision, "policy_id", "") or "unknown_policy")
        action = str(getattr(envelope.decision, "action", "") or "unknown_action")
        meta = dict(getattr(state, "meta", {}) or {})
        behavior = dict(getattr(state, "behavior", {}) or {})
        factors: list[str] = []
        if goal := str(behavior.get("goal") or meta.get("goal") or ""):
            factors.append(f"goal:{goal}")
        if dict(meta.get("constraints", {}) or {}):
            factors.append("constraints_present")
        if dict(meta.get("previous_feedback", {}) or {}):
            factors.append("feedback_present")
        if meta.get("signals"):
            factors.append("signals_present")
        if meta.get("profile"):
            factors.append("profile_present")
        autonomy_tier = str(meta.get("autonomy_tier") or "supervised")
        stored_policy = getattr(envelope, "policy", None) or getattr(envelope, "autonomy_decision", None)
        if isinstance(stored_policy, AutonomyDecision):
            decision = stored_policy
        else:
            decision = evaluate_autonomy_tier(
                action_type=action,
                autonomy_tier=autonomy_tier,
                approval_policy=dict(meta.get("approval_policy") or {}),
            )
        if decision.blocked_by_policy:
            factors.append(f"tier_blocked:{autonomy_tier}")
        elif decision.approval_required:
            factors.append(f"tier_requires_approval:{autonomy_tier}")
        elif decision.allowed:
            factors.append(f"tier_allowed:{autonomy_tier}")

        capability = get_action_capability(action)
        if capability.decisionable:
            factors.append(f"capability_class:{capability.action_class}")
        else:
            factors.append("capability_unknown")
        if not capability.prod_ready:
            factors.append("capability_not_prod_ready")
        if not capability.externally_verified:
            factors.append("capability_not_externally_verified")
        if capability.approval_required:
            factors.append("capability_requires_human_review")

        summary = f"{policy_id} selected {action}"
        if decision.blocked_by_policy:
            summary = f"{summary}; blocked by autonomy tier {autonomy_tier}"
        elif decision.approval_required:
            summary = f"{summary}; requires human approval in tier {autonomy_tier}"
        if not capability.prod_ready:
            summary = f"{summary}; capability says not prod-ready"
        if not capability.executable:
            summary = f"{summary}; capability says not directly executable"
        if not capability.externally_verified:
            summary = f"{summary}; capability says no external verification path"
        return PolicyExplanation(policy_id=policy_id, summary=summary, factors=tuple(factors))


__all__ = ["CANON_HEADLESS_POLICY_EXPLAINER", "PolicyExplanation", "PolicyExplainer"]
