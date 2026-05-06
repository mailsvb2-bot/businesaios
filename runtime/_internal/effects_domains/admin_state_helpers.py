from __future__ import annotations

from typing import Any

from runtime.observability.error_handling import swallow


def emit_user_setting_reset(event_log: Any, *, decision_id: str, correlation_id: str, admin_id: str) -> None:
    try:
        event_log.emit(
            event_type="user_setting_set",
            source="pricing.governance",
            user_id=str(admin_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"key": "admin:pricing_session", "value": {}},
        )
    except Exception:
        swallow(__name__, "runtime/_internal/effects_domains/admin_state_helpers.py")
