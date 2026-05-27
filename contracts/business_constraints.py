from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BusinessConstraints:
    currency: str = ''
    risk_tolerance: str = ''
    requires_manual_approval: bool = False
