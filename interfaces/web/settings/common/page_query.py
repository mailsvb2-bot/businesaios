from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageQuery:
    tenant_id: str
