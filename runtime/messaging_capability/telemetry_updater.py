from __future__ import annotations

from runtime.messaging_capability.channel_health import ChannelHealth
from runtime.messaging_capability.health_reason import resolve_health_reason
from runtime.messaging_capability.health_score_math import next_health_score
from runtime.messaging_capability.outcome_signal import classify_delivery_outcome_signal


class MessagingCapabilityTelemetryUpdater:
    """Transport-health updater only.

    This updater must not:
    - reorder business strategy
    - issue decisions
    - modify content
    """

    def __init__(self, *, registry):
        self._registry = registry

    def record_delivery_outcome(self, *, channel: str, ok: bool, meta: dict | None = None) -> ChannelHealth:
        current = self._registry.get(channel)
        signal = classify_delivery_outcome_signal(ok=bool(ok), meta=meta)
        if not signal.measurable:
            return current
        score = next_health_score(
            previous=float(current.health_score),
            ok=bool(signal.ok),
            blocked=bool(signal.blocked),
        )
        healthy = bool(signal.ok) or score > 0.35
        updated = ChannelHealth(
            channel=current.channel,
            healthy=healthy,
            health_score=score,
            reason=resolve_health_reason(ok=bool(signal.ok), meta=meta),
        )
        self._registry.set(updated)
        return updated
