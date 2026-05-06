from __future__ import annotations

from typing import Any


def emit_event(
    event_log: Any,
    *,
    event_type: str,
    event_name: str,
    payload: dict[str, object],
    source: str = 'demand_os',
) -> None:
    if event_log is None:
        return
    emit = getattr(event_log, 'emit', None)
    if not callable(emit):
        return
    safe_payload = dict(payload)
    emit(
        event_type=str(event_type),
        source=str(source),
        user_id=str(safe_payload.get('customer_id') or safe_payload.get('business_id') or 'unknown'),
        decision_id=str(safe_payload.get('decision_id') or safe_payload.get('request_id') or '-'),
        correlation_id=str(safe_payload.get('request_id') or safe_payload.get('session_id') or '-'),
        payload={'name': str(event_name), **safe_payload},
    )
