from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Conversion:
    conversion_id: str = ''
    lead_id: str = ''
    revenue: float = 0.0
