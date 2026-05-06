from __future__ import annotations

from collections.abc import Callable
from typing import Final


def render_business_quality_card(snapshot: object) -> dict[str, object]:
    return {
        'business_id': snapshot.business_id,
        'quality_score': snapshot.quality_score,
        'reason_codes': snapshot.reason_codes,
    }


def render_lead_delivery_card(outcome: object) -> dict[str, object]:
    return {
        'request_id': outcome.request_id,
        'status': outcome.delivery_status,
        'channel': outcome.channel,
    }


def render_live_demand_feed(rows: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    return list(rows)


def render_market_balance_card(snapshot: object) -> dict[str, object]:
    return {
        'utilization_ratio': snapshot.utilization_ratio,
        'concentration_ratio': snapshot.concentration_ratio,
    }


def render_revenue_route_card(channel: str, contribution: float) -> dict[str, object]:
    return {'channel': channel, 'contribution': float(contribution)}


def render_routing_reason_card(reason_codes: tuple[str, ...]) -> dict[str, object]:
    return {'reasons': tuple(reason_codes)}


DEMAND_COMPONENT_RENDERERS: Final[dict[str, Callable[..., object]]] = {
    'business_quality_card': render_business_quality_card,
    'lead_delivery_card': render_lead_delivery_card,
    'live_demand_feed': render_live_demand_feed,
    'market_balance_card': render_market_balance_card,
    'revenue_route_card': render_revenue_route_card,
    'routing_reason_card': render_routing_reason_card,
}

__all__ = tuple(DEMAND_COMPONENT_RENDERERS.values()) + ('DEMAND_COMPONENT_RENDERERS',)
