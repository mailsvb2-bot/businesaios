from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoadmapGuardTriggered:
    proposal_id: str
    product_id: str
    guard_code: str
    message: str
