from __future__ import annotations

from typing import Any, Dict, Optional

from runtime.security.runtime_asserts import assert_called_from_executor


class TrackingEffectsMixin:
    """Tracking-only effects.

    Emits events into the canonical event log WITHOUT sending UX.
    This is used to instrument callbacks/audio-progress signals/etc
    while keeping a single decision/action plan.
    """

    event_log: Any

    def track_event(
        self,
        *,
        decision_id: str | None,
        correlation_id: str | None,
        user_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "tracking",
    ) -> Any:
        assert_called_from_executor()

        et = str(event_type or "").strip()
        if not et:
            et = "tracking_event"

        self.event_log.emit(
            event_type=et,
            source=str(source or "tracking"),
            user_id=str(user_id),
            decision_id=(str(decision_id) if decision_id else None),
            correlation_id=(str(correlation_id) if correlation_id else None),
            payload=payload if isinstance(payload, dict) else {},
        )
        return {"ok": True}
