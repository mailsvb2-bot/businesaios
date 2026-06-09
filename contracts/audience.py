from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Audience:
    audience_id: str = ''
    summary: str = ''
    size_hint: float = 0.0
