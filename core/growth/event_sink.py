from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from core.events.log import EventLog
from core.tenancy.normalization import require_tenant_id
from core.tenancy.scope import TenantScope


@dataclass(frozen=True)
class EventLogSink:
    """Adapter from tenant-scoped EventLog into the small EventSink protocol.

    We accept both the current EventLog and the underlying store explicitly
    to avoid reaching into private fields.
    """

    event_store: Any
    default_event_log: EventLog

    def emit(self, *, tenant_id: str, user_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        # EventLog is tenant-scoped. If caller provided a different tenant_id,
        # we enforce by constructing a new scoped EventLog.
        tid = require_tenant_id(tenant_id)
        try:
            scoped = self.default_event_log
            if str(getattr(getattr(self.default_event_log, "_tenant", None), "tenant_id", "")) != tid:
                scoped = EventLog(self.event_store, tenant=TenantScope(tid))
        except Exception:
            scoped = self.default_event_log

        scoped.emit(
            event_type=str(event_type),
            source="ads",
            user_id=str(user_id or "system"),
            payload=dict(payload or {}),
        )
