from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CrmPaginationCursor:
    next_cursor: str | None = None


def parse_pagination_cursor(payload: Mapping[str, object]) -> CrmPaginationCursor:
    paging = payload.get('paging')
    if not isinstance(paging, Mapping):
        return CrmPaginationCursor()
    next_block = paging.get('next')
    if not isinstance(next_block, Mapping):
        return CrmPaginationCursor()
    cursor = next_block.get('after') or next_block.get('cursor')
    return CrmPaginationCursor(next_cursor=str(cursor) if cursor else None)
