from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentSignal:
    signal_id: str = ''
    page_type: str = ''
    engagement: str = ''
