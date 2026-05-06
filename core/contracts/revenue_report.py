from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from config.revenue_contract_policy import DEFAULT_REVENUE_CONTRACT_POLICY


@dataclass(frozen=True)
class RevenueReport:
    day: date
    impressions: int
    clicks: int
    purchases_success: int
    purchases_failed: int
    revenue: float
    ctr: float
    cr: float
    arpu: float

    top_offer_id: Optional[str] = None
    top_offer_revenue: float = field(default_factory=lambda: float(DEFAULT_REVENUE_CONTRACT_POLICY.zero_revenue))

    next_best_action_title: str = field(default_factory=lambda: DEFAULT_REVENUE_CONTRACT_POLICY.empty_title)
    next_best_action_text: str = field(default_factory=lambda: DEFAULT_REVENUE_CONTRACT_POLICY.empty_text)
