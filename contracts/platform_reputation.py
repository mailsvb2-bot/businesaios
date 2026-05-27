from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlatformReputation:
    platform: str = ''
    rating: float = 0.0
    review_count: str = ''
