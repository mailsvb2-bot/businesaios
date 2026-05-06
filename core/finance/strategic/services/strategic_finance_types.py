from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class StrategicFinanceDecision:
    forecast_version: str
    selected_scenario: str
    channel_allocation: dict[str, Decimal]
    runway_months: Decimal
    guard_codes: tuple[str, ...]
    decision_payload: dict[str, Any]
