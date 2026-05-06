from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass

from observability.tracing import TraceSpan


@dataclass(frozen=True)
class TraceExporter:
    def export(self, span: TraceSpan) -> dict:
        return {
            "trace_id": span.trace_id,
            "span_name": span.span_name,
            "attributes": dict(span.attributes),
        }
