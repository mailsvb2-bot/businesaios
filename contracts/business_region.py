from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BusinessRegion:
    country: str = ''
    city: str = ''
    timezone: str = ''
