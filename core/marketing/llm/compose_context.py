from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.telemetry.event_writer import TelemetryContext


@dataclass(frozen=True)
class ComposeContext:
    tenant_id: str
    user_id: str
    offer_id: str
    telemetry: TelemetryContext


def build_compose_context(inp: Any) -> ComposeContext:
    tenant_id = str(inp.tenant_id)
    user_id = str(inp.user_id)
    offer_id = str((inp.offer or {}).get("id", ""))
    telemetry = TelemetryContext(
        tenant_id=tenant_id,
        user_id=user_id,
        message_id=str(inp.message_id or ""),
        correlation_id=str(inp.correlation_id or ""),
    )
    return ComposeContext(
        tenant_id=tenant_id,
        user_id=user_id,
        offer_id=offer_id,
        telemetry=telemetry,
    )
