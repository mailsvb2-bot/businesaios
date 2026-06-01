from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KeywordSet:
    keyword_set_id: str = ''
    keywords: object = ()
    intent: str = ''
