from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANON_BUSINESS_MEMORY_MODELS = True


@dataclass(frozen=True)
class BusinessMemoryRecord:
    business_id: str
    profile: dict[str, Any] = field(default_factory=dict)
    active_channels: list[str] = field(default_factory=list)
    current_campaigns: list[dict[str, Any]] = field(default_factory=list)
    active_listings: list[dict[str, Any]] = field(default_factory=list)
    open_leads: list[dict[str, Any]] = field(default_factory=list)
    recent_runs: list[dict[str, Any]] = field(default_factory=list)
    last_verified_outcomes: list[dict[str, Any]] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    budget_envelope: dict[str, Any] = field(default_factory=dict)
    autonomy_tier: str = 'manual'
    operator_overrides: dict[str, Any] = field(default_factory=dict)
    escalation_history: list[dict[str, Any]] = field(default_factory=list)
    failed_strategies: list[dict[str, Any]] = field(default_factory=list)
    recurring_wins: list[dict[str, Any]] = field(default_factory=list)
    recurring_failures: list[dict[str, Any]] = field(default_factory=list)
    learned_preferences: dict[str, Any] = field(default_factory=dict)
    active_goals: list[str] = field(default_factory=list)
    operating_constraints: dict[str, Any] = field(default_factory=dict)
    aggregated_business_profile: dict[str, Any] = field(default_factory=dict)
    recent_external_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'business_id': str(self.business_id),
            'profile': dict(self.profile or {}),
            'active_channels': list(self.active_channels or []),
            'current_campaigns': [dict(item or {}) for item in self.current_campaigns or []],
            'active_listings': [dict(item or {}) for item in self.active_listings or []],
            'open_leads': [dict(item or {}) for item in self.open_leads or []],
            'recent_runs': [dict(item or {}) for item in self.recent_runs or []],
            'last_verified_outcomes': [dict(item or {}) for item in self.last_verified_outcomes or []],
            'blocked_actions': [str(item) for item in self.blocked_actions or [] if str(item).strip()],
            'budget_envelope': dict(self.budget_envelope or {}),
            'autonomy_tier': str(self.autonomy_tier or 'manual'),
            'operator_overrides': dict(self.operator_overrides or {}),
            'escalation_history': [dict(item or {}) for item in self.escalation_history or []],
            'failed_strategies': [dict(item or {}) for item in self.failed_strategies or []],
            'recurring_wins': [dict(item or {}) for item in self.recurring_wins or []],
            'recurring_failures': [dict(item or {}) for item in self.recurring_failures or []],
            'learned_preferences': dict(self.learned_preferences or {}),
            'active_goals': [str(item) for item in self.active_goals or [] if str(item).strip()],
            'operating_constraints': dict(self.operating_constraints or {}),
            'aggregated_business_profile': dict(self.aggregated_business_profile or {}),
            'recent_external_refs': [str(item) for item in self.recent_external_refs or [] if str(item).strip()],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None, *, business_id: str) -> BusinessMemoryRecord:
        data = dict(payload or {})
        return cls(
            business_id=str(data.get('business_id') or business_id),
            profile=dict(data.get('profile') or {}),
            active_channels=[str(item) for item in data.get('active_channels') or [] if str(item).strip()],
            current_campaigns=[dict(item or {}) for item in data.get('current_campaigns') or []],
            active_listings=[dict(item or {}) for item in data.get('active_listings') or []],
            open_leads=[dict(item or {}) for item in data.get('open_leads') or []],
            recent_runs=[dict(item or {}) for item in data.get('recent_runs') or []],
            last_verified_outcomes=[dict(item or {}) for item in data.get('last_verified_outcomes') or []],
            blocked_actions=[str(item) for item in data.get('blocked_actions') or [] if str(item).strip()],
            budget_envelope=dict(data.get('budget_envelope') or {}),
            autonomy_tier=str(data.get('autonomy_tier') or 'manual'),
            operator_overrides=dict(data.get('operator_overrides') or {}),
            escalation_history=[dict(item or {}) for item in data.get('escalation_history') or []],
            failed_strategies=[dict(item or {}) for item in data.get('failed_strategies') or []],
            recurring_wins=[dict(item or {}) for item in data.get('recurring_wins') or []],
            recurring_failures=[dict(item or {}) for item in data.get('recurring_failures') or []],
            learned_preferences=dict(data.get('learned_preferences') or {}),
            active_goals=[str(item) for item in data.get('active_goals') or [] if str(item).strip()],
            operating_constraints=dict(data.get('operating_constraints') or {}),
            aggregated_business_profile=dict(data.get('aggregated_business_profile') or {}),
            recent_external_refs=[str(item) for item in data.get('recent_external_refs') or [] if str(item).strip()],
        )


__all__ = ['CANON_BUSINESS_MEMORY_MODELS', 'BusinessMemoryRecord']
