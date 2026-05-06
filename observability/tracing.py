from __future__ import annotations

CANON_COMPAT_SHIM = True

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class TraceSpan:
    trace_id: str
    span_name: str
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def span_id(self) -> str:
        return self.trace_id

    @property
    def name(self) -> str:
        return self.span_name

    @property
    def fields(self) -> dict[str, Any]:
        return self.attributes

    @property
    def created_at(self) -> datetime:
        return datetime.now(timezone.utc)

    def as_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "span_name": self.span_name,
            "fields": dict(self.fields),
            "attributes": dict(self.attributes),
            "created_at": self.created_at.isoformat(),
        }


def start_span(span_name: str, **attributes: object) -> TraceSpan:
    return TraceSpan(
        trace_id=uuid.uuid4().hex,
        span_name=span_name,
        attributes=dict(attributes),
    )


@dataclass
class Tracer:
    spans: list[TraceSpan] = field(default_factory=list)

    def start(self, name: str, **fields: Any) -> TraceSpan:
        span = start_span(name, **fields)
        self.spans.append(span)
        return span

    def snapshot(self) -> list[dict[str, Any]]:
        return [span.as_dict() for span in self.spans]
