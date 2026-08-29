from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contracts.event_store import EventRecord

BUSINESS_FACT_EVENT_TYPE = "business_fact.v1"


@dataclass(frozen=True)
class BusinessFactV1:
    fact_id: str
    tenant_id: str
    business_id: str
    fact_type: str
    entity_id: str
    event_time_ms: int
    observed_at_ms: int
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    supersedes_fact_id: str | None = None
    decision_id: str | None = None
    correlation_id: str | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        for name in ("fact_id", "tenant_id", "business_id", "fact_type", "entity_id", "source"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} is required")

    def as_event(self) -> EventRecord:
        return {
            "event_id": self.fact_id,
            "tenant_id": self.tenant_id,
            "source": self.source,
            "event_type": BUSINESS_FACT_EVENT_TYPE,
            "timestamp_ms": int(self.observed_at_ms),
            "decision_id": self.decision_id,
            "correlation_id": self.correlation_id,
            "payload": {
                "schema_version": int(self.schema_version),
                "business_id": self.business_id,
                "fact_type": self.fact_type,
                "entity_id": self.entity_id,
                "event_time_ms": int(self.event_time_ms),
                "observed_at_ms": int(self.observed_at_ms),
                "payload": dict(self.payload),
                "provenance": dict(self.provenance),
                "supersedes_fact_id": self.supersedes_fact_id,
            },
        }


__all__ = ["BUSINESS_FACT_EVENT_TYPE", "BusinessFactV1"]
