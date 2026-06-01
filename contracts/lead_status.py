from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LeadStatus:
    status: str = ''
    is_closed: bool = False
    is_won: bool = False
