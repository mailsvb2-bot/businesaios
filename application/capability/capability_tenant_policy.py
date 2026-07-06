from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from application.autonomy.autonomy_tiers import ALLOWED_AUTONOMY_TIERS
from application.capability.capability_matrix import CapabilityRecord

CANON_CAPABILITY_TENANT_POLICY = True


def _text(value: object) -> str:
    return str(value or '').strip()


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_str_set(values: object) -> set[str]:
    if not isinstance(values, list | tuple | set | frozenset):
        return set()
    return {_text(value) for value in values if _text(value)}


@dataclass(frozen=True)
class CapabilityTenantPolicyVerdict:
    allowed: bool
    reason: str
    operator_required: bool = False
    recommended_autonomy_tier: str = 'supervised'
    policy_scope: str = 'default'
    metadata: dict[str, Any] = field(default_factory=dict)
    signals: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            'allowed': bool(self.allowed),
            'reason': str(self.reason),
            'operator_required': bool(self.operator_required),
            'recommended_autonomy_tier': str(self.recommended_autonomy_tier),
            'policy_scope': str(self.policy_scope),
            'metadata': dict(self.metadata),
            'signals': [dict(signal) for signal in self.signals],
        }


class CapabilityTenantPolicyService:
    """
    Tenant/business scoped capability policy facade.

    Important:
    - no goal selection
    - no decomposition
    - no second planner path
    - only applies explicit tenant/business/channel/region capability constraints
    """

    def _base_policy(self, *, request: Any) -> dict[str, Any]:
        meta = _safe_dict(getattr(request, 'meta', {}))
        constraints = _safe_dict(getattr(request, 'constraints', {}))
        profile = _safe_dict(getattr(request, 'profile', {}))
        policy: dict[str, Any] = {}
        for source in (profile.get('capability_policy'), constraints.get('capability_policy'), meta.get('capability_policy')):
            policy.update(_safe_dict(source))
        return policy

    def _policy_variants(self, *, request: Any) -> tuple[tuple[dict[str, Any], str], ...]:
        base = self._base_policy(request=request)
        if not base:
            return ()
        tenant_id = _text(getattr(request, 'tenant_id', ''))
        business_id = _text(getattr(request, 'business_id', ''))
        variants: list[tuple[dict[str, Any], str]] = [(base, 'tenant')]

        tenant_overrides = _safe_dict(base.get('tenant_overrides')).get(tenant_id)
        if isinstance(tenant_overrides, Mapping):
            variants.append(({**base, **_safe_dict(tenant_overrides)}, f'tenant:{tenant_id}'))

        business_overrides = _safe_dict(base.get('business_overrides')).get(business_id)
        if isinstance(business_overrides, Mapping):
            variants.append(({**base, **_safe_dict(business_overrides)}, f'business:{business_id}'))

        return tuple(variants)

    @staticmethod
    def _normalize_tier(tier: object, *, default: str) -> str:
        token = _text(tier) or default
        if token not in ALLOWED_AUTONOMY_TIERS:
            return default
        return token

    @staticmethod
    def _tier_rank(tier: str) -> int:
        try:
            return ALLOWED_AUTONOMY_TIERS.index(tier)
        except ValueError:
            return 0

    def _pick_stricter(self, *, current: CapabilityTenantPolicyVerdict | None, candidate: CapabilityTenantPolicyVerdict) -> CapabilityTenantPolicyVerdict:
        if current is None:
            return candidate
        if current.allowed and not candidate.allowed:
            return candidate
        if not current.allowed and candidate.allowed:
            return current
        if self._tier_rank(candidate.recommended_autonomy_tier) < self._tier_rank(current.recommended_autonomy_tier):
            return candidate
        if self._tier_rank(candidate.recommended_autonomy_tier) > self._tier_rank(current.recommended_autonomy_tier):
            return current
        if current.policy_scope == 'tenant' and candidate.policy_scope != 'tenant':
            return current
        if candidate.policy_scope == 'tenant' and current.policy_scope != 'tenant':
            return candidate
        if current.policy_scope.startswith('tenant:') and not candidate.policy_scope.startswith('tenant:'):
            return current
        if candidate.policy_scope.startswith('tenant:') and not current.policy_scope.startswith('tenant:'):
            return candidate
        return current

    def _evaluate_scope(self, *, request: Any, record: CapabilityRecord, policy: Mapping[str, Any], scope: str, payload: Mapping[str, Any] | None = None) -> CapabilityTenantPolicyVerdict:
        del payload
        action_type = record.action_type
        capability_key = record.capability_key
        autonomy_tier = self._normalize_tier(getattr(request, 'autonomy_tier', 'supervised'), default='supervised')
        business_id = _text(getattr(request, 'business_id', ''))
        tenant_id = _text(getattr(request, 'tenant_id', ''))
        channel = _text(getattr(request, 'channel', ''))
        region = _text(getattr(request, 'region', ''))

        disabled_businesses = _safe_str_set(policy.get('disabled_business_ids'))
        if business_id and business_id in disabled_businesses:
            return CapabilityTenantPolicyVerdict(False, 'business_capability_policy_denied', True, 'supervised', scope, {'business_id': business_id}, ({'code': 'business_blocked', 'business_id': business_id},))

        blocked_channels = _safe_str_set(policy.get('blocked_channels'))
        if channel and channel in blocked_channels:
            return CapabilityTenantPolicyVerdict(False, 'channel_capability_policy_denied', True, 'supervised', scope, {'channel': channel}, ({'code': 'channel_blocked', 'channel': channel},))

        blocked_regions = _safe_str_set(policy.get('blocked_regions'))
        if region and region in blocked_regions:
            return CapabilityTenantPolicyVerdict(False, 'region_capability_policy_denied', True, 'supervised', scope, {'region': region}, ({'code': 'region_blocked', 'region': region},))

        allowed_action_types = _safe_str_set(policy.get('allowed_action_types'))
        allowed_capability_keys = _safe_str_set(policy.get('allowed_capability_keys'))
        if allowed_action_types and action_type not in allowed_action_types:
            return CapabilityTenantPolicyVerdict(False, 'action_type_not_allowed_by_policy', True, 'supervised', scope, {'action_type': action_type, 'tenant_id': tenant_id}, ({'code': 'action_type_not_allowed', 'action_type': action_type},))
        if allowed_capability_keys and capability_key not in allowed_capability_keys:
            return CapabilityTenantPolicyVerdict(False, 'capability_key_not_allowed_by_policy', True, 'supervised', scope, {'capability_key': capability_key, 'tenant_id': tenant_id}, ({'code': 'capability_key_not_allowed', 'capability_key': capability_key},))

        disabled_action_types = _safe_str_set(policy.get('disabled_action_types'))
        disabled_capability_keys = _safe_str_set(policy.get('disabled_capability_keys'))
        if action_type in disabled_action_types:
            return CapabilityTenantPolicyVerdict(False, 'action_type_disabled_by_policy', True, 'supervised', scope, {'action_type': action_type}, ({'code': 'action_type_disabled', 'action_type': action_type},))
        if capability_key in disabled_capability_keys:
            return CapabilityTenantPolicyVerdict(False, 'capability_key_disabled_by_policy', True, 'supervised', scope, {'capability_key': capability_key}, ({'code': 'capability_key_disabled', 'capability_key': capability_key},))

        supervised_only_action_types = _safe_str_set(policy.get('supervised_only_action_types'))
        supervised_only_capability_keys = _safe_str_set(policy.get('supervised_only_capability_keys'))
        if autonomy_tier == 'full_autonomy' and (action_type in supervised_only_action_types or capability_key in supervised_only_capability_keys):
            return CapabilityTenantPolicyVerdict(False, 'policy_requires_supervised_autonomy', True, 'supervised', scope, {'action_type': action_type, 'capability_key': capability_key}, ({'code': 'supervised_only', 'action_type': action_type, 'capability_key': capability_key},))

        bounded_only_action_types = _safe_str_set(policy.get('bounded_only_action_types'))
        bounded_only_capability_keys = _safe_str_set(policy.get('bounded_only_capability_keys'))
        if autonomy_tier == 'full_autonomy' and (action_type in bounded_only_action_types or capability_key in bounded_only_capability_keys):
            return CapabilityTenantPolicyVerdict(False, 'policy_requires_bounded_autonomy', True, 'bounded_autonomy', scope, {'action_type': action_type, 'capability_key': capability_key}, ({'code': 'bounded_only', 'action_type': action_type, 'capability_key': capability_key},))

        max_tier_by_action = _safe_dict(policy.get('max_autonomy_tier_by_action_type'))
        max_tier_by_capability = _safe_dict(policy.get('max_autonomy_tier_by_capability_key'))
        max_tier = self._normalize_tier(max_tier_by_action.get(action_type) or max_tier_by_capability.get(capability_key), default=autonomy_tier)
        if self._tier_rank(autonomy_tier) > self._tier_rank(max_tier):
            return CapabilityTenantPolicyVerdict(False, 'policy_autonomy_tier_exceeded', True, max_tier, scope, {'action_type': action_type, 'capability_key': capability_key, 'max_autonomy_tier': max_tier}, ({'code': 'autonomy_tier_exceeded', 'max_autonomy_tier': max_tier},))

        return CapabilityTenantPolicyVerdict(True, 'tenant_policy_allowed', False, autonomy_tier, scope)

    def evaluate(self, *, request: Any, record: CapabilityRecord, payload: Mapping[str, Any] | None = None) -> CapabilityTenantPolicyVerdict:
        policies = self._policy_variants(request=request)
        autonomy_tier = self._normalize_tier(getattr(request, 'autonomy_tier', 'supervised'), default='supervised')
        if not policies:
            return CapabilityTenantPolicyVerdict(allowed=True, reason='no_tenant_policy', recommended_autonomy_tier=autonomy_tier)

        verdict: CapabilityTenantPolicyVerdict | None = None
        for policy, scope in policies:
            candidate = self._evaluate_scope(request=request, record=record, payload=payload, policy=policy, scope=scope)
            verdict = self._pick_stricter(current=verdict, candidate=candidate)
        return verdict or CapabilityTenantPolicyVerdict(allowed=True, reason='tenant_policy_allowed', recommended_autonomy_tier=autonomy_tier)


__all__ = ['CANON_CAPABILITY_TENANT_POLICY', 'CapabilityTenantPolicyVerdict', 'CapabilityTenantPolicyService']
