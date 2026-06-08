from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lead:
    lead_id: str = ''
    source: str = ''
    status: str = ''
