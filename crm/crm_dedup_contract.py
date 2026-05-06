from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrmDedupMatch:
    matched: bool
    record_id: str | None
    confidence: float
    reason: str
