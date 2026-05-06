from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Article:
    article_id: str = ''
    title: str = ''
    slug: str = ''
