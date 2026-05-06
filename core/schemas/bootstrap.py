from __future__ import annotations

from .registry import SchemaRegistry
from .base import SchemaId
from .event_schemas import UserTransitEventV1
from .worldstate_schema import WorldStateSchemaV1
from .decision_schema import DecisionEnvelopeV1


def build_schema_registry() -> SchemaRegistry:
    reg = SchemaRegistry()

    reg.register(SchemaId("event.user_transit", 1), UserTransitEventV1())
    reg.register(SchemaId("world_state", 1), WorldStateSchemaV1())
    reg.register(SchemaId("decision_envelope", 1), DecisionEnvelopeV1())

    return reg
