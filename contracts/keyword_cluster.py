from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class KeywordCluster:
    cluster_id: str = ''
    primary_keyword: str = ''
    keywords: object = ()
