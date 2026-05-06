from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class GrowthBudgetGuardrailsPolicy:
    max_budget_increase_pct: float = 10.0
    allow_creative_changes: bool = False
    change_window_utc_start: int = 6
    change_window_utc_end: int = 20
    zero_spend_floor: float = 0.0
    ads_guardrails_block_event_type: str = "ads_guardrails_block"
    no_budget_limit_reason: str = "NO_BUDGET_LIMIT"
    ok_reason: str = "OK"
    daily_budget_exceeded_reason: str = "DAILY_BUDGET_EXCEEDED"


DEFAULT_GROWTH_BUDGET_GUARDRAILS_POLICY = GrowthBudgetGuardrailsPolicy()
