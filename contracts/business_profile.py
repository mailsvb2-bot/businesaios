from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessProfile:
    business_id: str = ''
    name: str = ''
    goal: str = ''
    region: str = ''
