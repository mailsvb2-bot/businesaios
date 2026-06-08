from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdCreative:
    creative_id: str = ''
    headline: str = ''
    cta: str = ''
