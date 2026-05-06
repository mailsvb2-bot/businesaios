from __future__ import annotations

from typing import Any

from observability.demand.event_types import emit_typed

CANON_OBSERVABILITY_DEMAND_ALIAS_NAMESPACE = True
CANON_OBSERVABILITY_DEMAND_PACKAGE_OWNER = True

DELIVERY_EVENTS_TYPE = "delivery_events"
DEMAND_EVENTS_TYPE = "demand_events"
INTENT_EVENTS_TYPE = "intent_events"
MARKET_BALANCE_EVENTS_TYPE = "market_balance_events"
MATCH_EVENTS_TYPE = "match_events"
OUTCOME_EVENTS_TYPE = "outcome_events"
QUALITY_EVENTS_TYPE = "quality_events"
ROUTING_EVENTS_TYPE = "routing_events"

def emit_delivery_events(event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    emit_typed(DELIVERY_EVENTS_TYPE, event_log, event_name, payload)

def emit_demand_events(event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    emit_typed(DEMAND_EVENTS_TYPE, event_log, event_name, payload)

def emit_intent_events(event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    emit_typed(INTENT_EVENTS_TYPE, event_log, event_name, payload)

def emit_market_balance_events(event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    emit_typed(MARKET_BALANCE_EVENTS_TYPE, event_log, event_name, payload)

def emit_match_events(event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    emit_typed(MATCH_EVENTS_TYPE, event_log, event_name, payload)

def emit_outcome_events(event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    emit_typed(OUTCOME_EVENTS_TYPE, event_log, event_name, payload)

def emit_quality_events(event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    emit_typed(QUALITY_EVENTS_TYPE, event_log, event_name, payload)

def emit_routing_events(event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    emit_typed(ROUTING_EVENTS_TYPE, event_log, event_name, payload)

__all__ = [
    "CANON_OBSERVABILITY_DEMAND_ALIAS_NAMESPACE",
    "CANON_OBSERVABILITY_DEMAND_PACKAGE_OWNER",
    "DELIVERY_EVENTS_TYPE",
    "DEMAND_EVENTS_TYPE",
    "INTENT_EVENTS_TYPE",
    "MARKET_BALANCE_EVENTS_TYPE",
    "MATCH_EVENTS_TYPE",
    "OUTCOME_EVENTS_TYPE",
    "QUALITY_EVENTS_TYPE",
    "ROUTING_EVENTS_TYPE",
    "emit_delivery_events",
    "emit_demand_events",
    "emit_intent_events",
    "emit_market_balance_events",
    "emit_match_events",
    "emit_outcome_events",
    "emit_quality_events",
    "emit_routing_events",
]
