from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RewardSignal:
    """A minimal reward signal derived from proof events."""

    user_id: str
    event_type: str
    value: float
    timestamp_ms: int


class RewardModel:
    """Pure reward derivation from events.

    This is intentionally minimal: the learning loop is offline and must remain
    reproducible from the event-store.
    """

    def reward_for_event(self, event: dict) -> RewardSignal | None:
        et = str(event.get("event_type") or "")
        if et in ("payment_succeeded", "payment_captured"):
            return RewardSignal(
                user_id=str(event.get("user_id") or "unknown"),
                event_type=et,
                value=1.0,
                timestamp_ms=int(event.get("timestamp_ms") or 0),
            )
        return None
