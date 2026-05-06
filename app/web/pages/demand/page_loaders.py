from __future__ import annotations

from collections.abc import Callable
from typing import Final


def load_rows(rows: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
    return tuple(dict(row) for row in rows)


def build_page_loader(page_name: str) -> Callable[[tuple[dict[str, object], ...]], tuple[dict[str, object], ...]]:
    normalized = str(page_name).strip()
    if not normalized:
        raise ValueError('page_name must be non-empty')

    def load(rows: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
        return load_rows(rows)

    return load


def load_demand_overview(snapshot: object) -> dict[str, object]:
    return {
        'requests': snapshot.request_count,
        'decisions': snapshot.decision_count,
        'deliveries': snapshot.delivery_count,
    }


def load_market_health(snapshot: object) -> dict[str, object]:
    return snapshot.__dict__ if hasattr(snapshot, '__dict__') else {}


def load_marketplace_settings(settings: dict[str, object]) -> dict[str, object]:
    return dict(settings)


def load_revenue_from_demand(rows: tuple[dict[str, object], ...]) -> float:
    return sum(float(row.get('revenue') or 0.0) for row in rows)


DEMAND_PAGE_LOADERS: Final[dict[str, Callable[..., object]]] = {
    'business_quality': build_page_loader('business_quality'),
    'incoming_demand': build_page_loader('incoming_demand'),
    'routing_decisions': build_page_loader('routing_decisions'),
    'demand_overview': load_demand_overview,
    'market_health': load_market_health,
    'marketplace_settings': load_marketplace_settings,
    'revenue_from_demand': load_revenue_from_demand,
}

__all__ = (
    'DEMAND_PAGE_LOADERS',
    'build_page_loader',
    'load_rows',
    'load_demand_overview',
    'load_market_health',
    'load_marketplace_settings',
    'load_revenue_from_demand',
)
