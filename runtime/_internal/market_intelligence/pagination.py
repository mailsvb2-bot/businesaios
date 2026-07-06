from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

CANON_MARKET_INTELLIGENCE_PAGINATION = True


@dataclass(frozen=True)
class PageCursor:
    token: str | None = None
    page_number: int = 1


@dataclass(frozen=True)
class PageResult:
    items: tuple[dict[str, Any], ...]
    next_cursor: PageCursor | None = None
    exhausted: bool = False
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class PaginationSummary:
    rows: tuple[dict[str, Any], ...]
    pages_fetched: int
    final_cursor_token: str | None
    exhausted: bool
    page_metadata: tuple[dict[str, Any], ...]


class PaginationWindow:
    def __init__(self, *, max_pages: int = 20, max_items: int = 500) -> None:
        self._max_pages = max(1, int(max_pages))
        self._max_items = max(1, int(max_items))

    def collect(self, fetch_page: Callable[[PageCursor | None], PageResult]) -> tuple[dict[str, Any], ...]:
        return self.collect_summary(fetch_page).rows

    def collect_summary(self, fetch_page: Callable[[PageCursor | None], PageResult]) -> PaginationSummary:
        cursor: PageCursor | None = None
        page_number = 0
        rows: list[dict[str, Any]] = []
        page_metadata: list[dict[str, Any]] = []
        final_cursor_token: str | None = None
        exhausted = False
        while page_number < self._max_pages and len(rows) < self._max_items:
            result = fetch_page(cursor)
            page_number += 1
            page_metadata.append(dict(result.metadata or {}))
            for item in result.items:
                rows.append(dict(item))
                if len(rows) >= self._max_items:
                    break
            final_cursor_token = result.next_cursor.token if result.next_cursor and result.next_cursor.token else final_cursor_token
            exhausted = bool(result.exhausted or result.next_cursor is None)
            if exhausted:
                break
            cursor = result.next_cursor
        return PaginationSummary(
            rows=tuple(rows[: self._max_items]),
            pages_fetched=page_number,
            final_cursor_token=final_cursor_token,
            exhausted=exhausted,
            page_metadata=tuple(page_metadata),
        )


def normalize_items(value: object) -> tuple[dict[str, Any], ...]:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return tuple(dict(item) for item in value if isinstance(item, Mapping))
    return ()


__all__ = [
    'CANON_MARKET_INTELLIGENCE_PAGINATION',
    'PageCursor',
    'PageResult',
    'PaginationSummary',
    'PaginationWindow',
    'normalize_items',
]
