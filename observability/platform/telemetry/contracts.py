from __future__ import annotations

from typing import Any, Protocol


class AppendOnlyTelemetryStore(Protocol):
    def append(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None: ...
