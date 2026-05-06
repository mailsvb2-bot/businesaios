from __future__ import annotations

from typing import Any, Mapping

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging_policy.policy_plan import PolicyPlan

_FORBIDDEN_POLICY_KEYS = {
    "llm_ranker",
    "llm_prompt",
    "ai_strategy",
    "decision_score",
    "world_model_score",
    "policy_override",
}


class MessagingPolicyDisciplineViolation(ValueError):
    pass


def _dedupe(items) -> tuple[str, ...]:
    out: list[str] = []
    for item in tuple(items or ()):
        out.append(normalize_channel(item))
    return tuple(dict.fromkeys(out))


def ensure_policy_input_disciplined(channel_policy: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(channel_policy or {})
    forbidden = sorted(key for key in raw if key in _FORBIDDEN_POLICY_KEYS)
    if forbidden:
        raise MessagingPolicyDisciplineViolation(
            "messaging policy accepts deterministic delivery inputs only: " + ", ".join(forbidden)
        )
    out = dict(raw)
    out["fallback_channels"] = list(_dedupe(raw.get("fallback_channels") or ()))
    out["attempt_index"] = max(0, int(raw.get("attempt_index") or 0))
    out["unanswered_threshold_s"] = max(0, int(raw.get("unanswered_threshold_s") or 0))
    out["verified_only"] = bool(raw.get("verified_only", False))
    requirement = raw.get("required_capabilities")
    out["required_capabilities"] = dict(requirement) if isinstance(requirement, Mapping) else {}
    return out


def ensure_policy_plan_disciplined(plan: PolicyPlan) -> PolicyPlan:
    ordered = tuple(_dedupe(plan.ordered_channels))
    reasons = tuple(dict.fromkeys(str(x) for x in tuple(plan.reason_codes or ()) if str(x).strip()))
    if ordered and not reasons:
        raise MessagingPolicyDisciplineViolation("messaging policy plan must explain why ordered channels were produced")
    if not ordered and not str(plan.terminal_reason or "").strip():
        raise MessagingPolicyDisciplineViolation("empty messaging policy plan must carry terminal_reason")
    return PolicyPlan(ordered_channels=ordered, reason_codes=reasons, terminal_reason=str(plan.terminal_reason or ""))
