"""Telemetry writer (canonical).

The Ring requires a strict event schema. The canonical implementation that
enforces this is :class:`core.events.log.EventLog`.

Historically, some modules used a direct "append_event" helper that attempted
to support multiple event store signatures. That creates a dangerous "second
line" of event semantics.

This module keeps the public helper *name* for compatibility, but routes all
writes through the canonical EventLog so we never bypass schema validation or
tenant scoping.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.events.log import EventLog
from core.tenancy.scope import TenantScope


@dataclass(frozen=True)
class TelemetryContext:
    """Minimal context for emitting telemetry events."""

    tenant_id: str
    user_id: str
    session_id: str = ""
    trace_id: str = ""
    message_id: str = ""
    correlation_id: str = ""


def _now_ms() -> int:
    return int(time.time() * 1000)


async def append_event(
    event_store: Any,
    *,
    event_type: str,
    ctx: TelemetryContext,
    payload: dict[str, Any],
    ts_ms: int | None = None,
    source: str = "telemetry",
) -> None:
    """Append an event into the canonical event stream.

    Notes:
      - Keeps async signature for callers.
      - Writes via EventLog (strict schema + tenant scoping).
      - Context fields are persisted inside payload (except correlation_id).
    """

    if event_store is None:
        return

    ts = int(ts_ms or _now_ms())
    log = EventLog(event_store, tenant=TenantScope(str(ctx.tenant_id)))

    enriched = dict(payload or {})
    if ctx.session_id:
        enriched.setdefault("session_id", ctx.session_id)
    if ctx.trace_id:
        enriched.setdefault("trace_id", ctx.trace_id)
    if ctx.message_id:
        enriched.setdefault("message_id", ctx.message_id)

    corr = (ctx.correlation_id or ctx.trace_id or ctx.message_id or None)

    # EventLog.emit is sync; keep this helper async for API stability.
    log.emit(
        event_type=str(event_type),
        source=str(source),
        user_id=str(ctx.user_id),
        payload=enriched,
        correlation_id=corr,
        timestamp_ms=ts,
        decision_id=None,
    )
