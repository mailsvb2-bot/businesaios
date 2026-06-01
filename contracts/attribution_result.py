from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AttributionResult:
    attribution_id: str = ''
    channel: str = ''
    credit: float = 0.0
