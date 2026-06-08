from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LandingPage:
    page_id: str = ''
    url: str = ''
    intent: str = ''
