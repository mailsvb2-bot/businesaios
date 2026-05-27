from __future__ import annotations

from dataclasses import dataclass

CANON_BUSINESS_MEMORY_POLICY = True


@dataclass(frozen=True)
class BusinessMemoryPolicy:
    max_recent_runs: int = 20
    max_verified_outcomes: int = 20
    max_failed_strategies: int = 20
    max_external_refs: int = 25
    max_active_channels: int = 12
    max_campaigns: int = 10
    max_listings: int = 10
    max_open_leads: int = 20
    max_blocked_actions: int = 25
    max_escalation_history: int = 20
    max_recurring_items: int = 8
    recurring_win_threshold: int = 2
    recurring_failure_threshold: int = 2


DEFAULT_BUSINESS_MEMORY_POLICY = BusinessMemoryPolicy()


__all__ = [
    'CANON_BUSINESS_MEMORY_POLICY',
    'BusinessMemoryPolicy',
    'DEFAULT_BUSINESS_MEMORY_POLICY',
]
