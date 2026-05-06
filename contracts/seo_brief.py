from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SeoBrief:
    brief_id: str = ''
    primary_keyword: str = ''
    intent: str = ''
