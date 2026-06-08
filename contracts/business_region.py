from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessRegion:
    country: str = ''
    city: str = ''
    timezone: str = ''
