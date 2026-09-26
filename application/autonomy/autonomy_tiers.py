from __future__ import annotations

from typing import Any

from contracts.policy_decision import PolicyDecisionV1
from execution.action_catalog import classify_action_type, normalize_action_type

CANON_HEADLESS_AUTONOMY_TIERS = True
CANON_AUTONOMY_TRANSITION_FAILS_CLOSED = True

CANONICAL_AUTONOMY_TIERS: tuple[str, ...] = (
    "observe",
    "advisory",
    "draft",
    "approval_required",
    "supervised",
    "autonomous_bounded",
)

LEGACY_AUTONOMY_TIER_ALIASES: dict[str, str] = {
    "bounded_autonomy": "autonomous_bounded",
    "full_autonomy": "autonomous_bounded",
}

# Public input surface remains backward compatible while all policy evaluation
# emits one of the six canonical levels.
ALLOWED_AUTONOMY_TIERS: tuple[str, ...] = (
    *CANONICAL_AUTONOMY_TIERS,
    *LEGACY_AUTONOMY_TIER_ALIASES,
)

_AUTONOMY_TIER_RANK: dict[str, int] = {
    tier: index for index, tier in enumerate(CANONICAL_AUTONOMY_TIERS)
}


AutonomyDecision = PolicyDecisionV1  # compatibility alias; semantic owner is contracts.policy_decision


def normalize_autonomy_tier(value: object, *, default: str = "supervised") -> str:
    token = str(value or "").strip().lower()
    token = LEGACY_AUTONOMY_TIER_ALIASES.get(token, token)
    if token in CANONICAL_AUTONOMY_TIERS:
        return token
    fallback = str(default or "supervised").strip().lower()
    fallback = LEGACY_AUTONOMY_TIER_ALIASES.get(fallback, fallback)
    return fallback if fallback in CANONICAL_AUTONOMY_TIERS else "supervised"


def autonomy_tier_rank(value: object) -> int:
    return _AUTONOMY_TIER_RANK[normalize_autonomy_tier(value)]


_TIER_POLICY: dict[str, dict[str, set[str]]] = {
    # OBSERVE and ADVISORY never authorize a side effect.
    "observe": {
        "allowed": {"read_only"},
        "approval_required": set(),
        "forbidden": {
            "ads_write", "budget_change", "platform_listing_write", "communications_write",
            "marketplace_routing", "seo_publish", "profile_publish", "internal_execution", "unknown",
        },
    },
    "advisory": {
        "allowed": {"read_only"},
        "approval_required": set(),
        "forbidden": {
            "ads_write", "budget_change", "platform_listing_write", "communications_write",
            "marketplace_routing", "seo_publish", "profile_publish", "internal_execution", "unknown",
        },
    },
    # DRAFT may prepare internal artifacts but cannot perform an external effect.
    "draft": {
        "allowed": {"read_only", "internal_execution"},
        "approval_required": set(),
        "forbidden": {
            "ads_write", "budget_change", "platform_listing_write", "communications_write",
            "marketplace_routing", "seo_publish", "profile_publish", "unknown",
        },
    },
    # APPROVAL_REQUIRED makes effectful capabilities explicit human handoffs.
    "approval_required": {
        "allowed": {"read_only", "internal_execution"},
        "approval_required": {
            "ads_write", "budget_change", "platform_listing_write", "communications_write",
            "marketplace_routing", "seo_publish", "profile_publish", "unknown",
        },
        "forbidden": set(),
    },
    "supervised": {
        "allowed": {
            "read_only", "platform_listing_write", "communications_write",
            "marketplace_routing", "seo_publish", "profile_publish", "internal_execution",
        },
        "approval_required": {"ads_write", "budget_change", "unknown"},
        "forbidden": set(),
    },
    "autonomous_bounded": {
        "allowed": {"read_only", "communications_write", "marketplace_routing", "seo_publish", "internal_execution"},
        "approval_required": {"platform_listing_write", "profile_publish"},
        "forbidden": {"ads_write", "budget_change", "unknown"},
    },
}


def evaluate_autonomy_tier(*, action_type: str, autonomy_tier: str, approval_policy: dict[str, Any] | None = None) -> AutonomyDecision:
    tier = normalize_autonomy_tier(autonomy_tier)
    normalized_action_type = normalize_action_type(action_type)
    action_class = classify_action_type(normalized_action_type)
    policy = _TIER_POLICY[tier]
    allowed = action_class in policy["allowed"]
    approval_required = action_class in policy["approval_required"]
    blocked = action_class in policy["forbidden"]

    approval = dict(approval_policy or {})
    capability_policy = dict(approval.get("capability_matrix") or {})
    always_operator_classes = {str(v) for v in capability_policy.get("always_operator_action_classes") or []}
    never_bounded_classes = {
        str(v)
        for v in (
            capability_policy.get("never_autonomous_bounded_action_classes")
            or capability_policy.get("never_full_autonomy_action_classes")
            or []
        )
    }
    always_operator_types = {normalize_action_type(str(v)) for v in capability_policy.get("always_operator_action_types") or []}
    never_bounded_types = {
        normalize_action_type(str(v))
        for v in (
            capability_policy.get("never_autonomous_bounded_action_types")
            or capability_policy.get("never_full_autonomy_action_types")
            or []
        )
    }

    if action_class in {str(v) for v in approval.get("allow_action_classes") or []}:
        blocked = False
        approval_required = False
        allowed = True
    if normalized_action_type in {normalize_action_type(str(v)) for v in approval.get("allow_action_types") or []}:
        blocked = False
        approval_required = False
        allowed = True
    if action_class in always_operator_classes or normalized_action_type in always_operator_types:
        approval_required = True
        allowed = False
    if tier == "autonomous_bounded" and (
        action_class in never_bounded_classes or normalized_action_type in never_bounded_types
    ):
        approval_required = True
        blocked = False
        allowed = False
    if action_class in {str(v) for v in approval.get("require_human_action_classes") or []}:
        approval_required = True
        blocked = False
        allowed = False
    if normalized_action_type in {normalize_action_type(str(v)) for v in approval.get("block_action_types") or []}:
        blocked = True
        approval_required = False
        allowed = False
    if action_class in {str(v) for v in approval.get("block_action_classes") or []}:
        blocked = True
        approval_required = False
        allowed = False

    handoff_reason = None
    if blocked:
        handoff_reason = f"autonomy_tier_blocked:{tier}:{action_class}"
    elif approval_required:
        handoff_reason = f"autonomy_tier_requires_approval:{tier}:{action_class}"

    return AutonomyDecision(
        tier=tier,
        action_type=str(action_type or ""),
        action_class=action_class,
        allowed=bool(allowed and not blocked and not approval_required),
        approval_required=bool(approval_required and not blocked),
        blocked_by_policy=bool(blocked),
        handoff_reason=handoff_reason,
    )


def _restriction_rank(decision: AutonomyDecision) -> int:
    if decision.blocked_by_policy:
        return 3
    if decision.approval_required:
        return 2
    if not decision.allowed:
        return 1
    return 0


def evaluate_autonomy_transition(
    *,
    decided_action_type: str,
    executable_action_type: str,
    autonomy_tier: str,
    approval_policy: dict[str, Any] | None = None,
) -> AutonomyDecision:
    """Authorize the sovereign intent and executable projection at one canonical tier."""

    decided = evaluate_autonomy_tier(
        action_type=decided_action_type,
        autonomy_tier=autonomy_tier,
        approval_policy=approval_policy,
    )
    executable = evaluate_autonomy_tier(
        action_type=executable_action_type,
        autonomy_tier=autonomy_tier,
        approval_policy=approval_policy,
    )
    if _restriction_rank(decided) >= _restriction_rank(executable):
        return decided
    return executable


__all__ = [
    "CANON_AUTONOMY_TRANSITION_FAILS_CLOSED",
    "CANON_HEADLESS_AUTONOMY_TIERS",
    "CANONICAL_AUTONOMY_TIERS",
    "LEGACY_AUTONOMY_TIER_ALIASES",
    "ALLOWED_AUTONOMY_TIERS",
    "AutonomyDecision",
    "autonomy_tier_rank",
    "classify_action_type",
    "evaluate_autonomy_tier",
    "evaluate_autonomy_transition",
    "normalize_autonomy_tier",
]
