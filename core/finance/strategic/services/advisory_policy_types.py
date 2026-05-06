from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class StrategicFinanceAdvice:
    selected_scenario: str
    channel_allocation: dict[str, Decimal]
    runway_months: Decimal
    guard_codes: tuple[str, ...]
    scenario_scores: dict[str, Decimal]
    rejection_reasons: dict[str, tuple[str, ...]]
    evidence_trail: tuple[str, ...]
    allocation_rationale: tuple[str, ...]
    liquidity_mode: str
