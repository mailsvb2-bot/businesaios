from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttributionResult:
    attribution_id: str = ''
    channel: str = ''
    credit: float = 0.0
