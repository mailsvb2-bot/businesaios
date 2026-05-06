from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DownsideRiskDetected:
    risk_score: Decimal
