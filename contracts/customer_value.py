from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CustomerValue:
    customer_id: str = ''
    ltv: float = 0.0
    payback_days: float = 0.0
