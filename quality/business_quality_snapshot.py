from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BusinessQualitySnapshot:
    business_id: str
    quality_score: float
    reason_codes: tuple[str, ...]
