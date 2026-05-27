from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.action_catalog import classify_action_type, normalize_action_type

CANON_HEADLESS_AUTONOMY_TIERS = True

ALLOWED_AUTONOMY_TIERS: tuple[str, ...] = (
    'advisory',
    'supervised',
    'bounded_autonomy',
    'full_autonomy',
)


@dataclass(frozen=True)
class AutonomyDecision:
    tier: str
    action_type: str
    action_class: str
    allowed: bool
    approval_required: bool
    blocked_by_policy: bool
    handoff_reason: str | None = None







_TIER_POLICY: dict[str, dict[str, set[str]]] = {
    'advisory': {
        'allowed': {'read_only'},
        'approval_required': set(),
        'forbidden': {
            'ads_write', 'budget_change', 'platform_listing_write', 'communications_write',
            'marketplace_routing', 'seo_publish', 'profile_publish', 'internal_execution', 'unknown',
        },
    },
    'supervised': {
        'allowed': {
            'read_only', 'platform_listing_write', 'communications_write',
            'marketplace_routing', 'seo_publish', 'profile_publish', 'internal_execution',
        },
        'approval_required': {'ads_write', 'budget_change', 'unknown'},
        'forbidden': set(),
    },
    'bounded_autonomy': {
        'allowed': {'read_only', 'communications_write', 'marketplace_routing', 'seo_publish', 'internal_execution'},
        'approval_required': {'platform_listing_write', 'profile_publish'},
        'forbidden': {'ads_write', 'budget_change', 'unknown'},
    },
    'full_autonomy': {
        'allowed': {
            'read_only', 'ads_write', 'budget_change', 'platform_listing_write',
            'communications_write', 'marketplace_routing', 'seo_publish', 'profile_publish', 'internal_execution',
        },
        'approval_required': {'unknown'},
        'forbidden': set(),
    },
}


def evaluate_autonomy_tier(*, action_type: str, autonomy_tier: str, approval_policy: dict[str, Any] | None = None) -> AutonomyDecision:
    tier = str(autonomy_tier or 'supervised').strip() or 'supervised'
    if tier not in ALLOWED_AUTONOMY_TIERS:
        tier = 'supervised'
    normalized_action_type = normalize_action_type(action_type)
    action_class = classify_action_type(normalized_action_type)
    policy = _TIER_POLICY.get(tier, _TIER_POLICY['supervised'])
    allowed = action_class in policy['allowed']
    approval_required = action_class in policy['approval_required']
    blocked = action_class in policy['forbidden']

    approval = dict(approval_policy or {})
    capability_policy = dict(approval.get('capability_matrix') or {})
    always_operator_classes = {str(v) for v in capability_policy.get('always_operator_action_classes') or []}
    never_full_classes = {str(v) for v in capability_policy.get('never_full_autonomy_action_classes') or []}
    always_operator_types = {normalize_action_type(str(v)) for v in capability_policy.get('always_operator_action_types') or []}
    never_full_types = {normalize_action_type(str(v)) for v in capability_policy.get('never_full_autonomy_action_types') or []}

    if action_class in {str(v) for v in approval.get('allow_action_classes') or []}:
        blocked = False
        approval_required = False
        allowed = True
    if normalized_action_type in {normalize_action_type(str(v)) for v in approval.get('allow_action_types') or []}:
        blocked = False
        approval_required = False
        allowed = True
    if action_class in always_operator_classes or normalized_action_type in always_operator_types:
        approval_required = True
        allowed = False
    if tier == 'full_autonomy' and (action_class in never_full_classes or normalized_action_type in never_full_types):
        approval_required = True
        allowed = False
    if action_class in {str(v) for v in approval.get('require_human_action_classes') or []}:
        approval_required = True
        allowed = False
    if normalized_action_type in {normalize_action_type(str(v)) for v in approval.get('block_action_types') or []}:
        blocked = True
        allowed = False
    if action_class in {str(v) for v in approval.get('block_action_classes') or []}:
        blocked = True
        allowed = False

    handoff_reason = None
    if blocked:
        handoff_reason = f'autonomy_tier_blocked:{tier}:{action_class}'
    elif approval_required:
        handoff_reason = f'autonomy_tier_requires_approval:{tier}:{action_class}'

    return AutonomyDecision(
        tier=tier,
        action_type=str(action_type or ''),
        action_class=action_class,
        allowed=bool(allowed and not blocked and not approval_required),
        approval_required=bool(approval_required and not blocked),
        blocked_by_policy=bool(blocked),
        handoff_reason=handoff_reason,
    )


__all__ = [
    'CANON_HEADLESS_AUTONOMY_TIERS',
    'ALLOWED_AUTONOMY_TIERS',
    'AutonomyDecision',
    'classify_action_type',
    'evaluate_autonomy_tier',
]
