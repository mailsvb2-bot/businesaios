from __future__ import annotations

from typing import Any

from observability.demand._emitter import emit_event


class DemandAuditLog:
    def __init__(self, *, max_rows: int = 1000) -> None:
        self._rows: list[dict[str, object]] = []
        self._max_rows = max(1, int(max_rows))

    def append(self, row: dict[str, object]) -> None:
        self._rows.append(dict(row))
        if len(self._rows) > self._max_rows:
            self._rows = self._rows[-self._max_rows :]

    def rows(self) -> tuple[dict[str, object], ...]:
        return tuple(self._rows)

    def publish(self, event_log: Any, event_name: str = 'demand_audit') -> None:
        emit_event(
            event_log,
            event_type='demand_audit_log',
            event_name=event_name,
            payload={'rows': [dict(r) for r in self._rows[-100:]]},
        )
