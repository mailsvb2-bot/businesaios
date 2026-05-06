from __future__ import annotations

from runtime.messaging_capability.health_filter import filter_channels_by_health
from runtime.messaging_capability.route_filter import filter_channels_by_capability
from runtime.messaging_capability.router_result import MessagingCapabilityRouteResult


class MessagingCapabilityRouter:
    """Deterministic transport routing only.

    This router must not:
    - rank business strategy
    - change message text
    - issue actions
    - bypass canonical execution
    """

    def __init__(self, *, health_registry=None):
        self._health_registry = health_registry

    def route(self, *, ordered_channels: tuple[str, ...], requirement) -> MessagingCapabilityRouteResult:
        reasons: list[str] = []
        channels = tuple(ordered_channels or ())
        channels = filter_channels_by_capability(ordered_channels=channels, requirement=requirement)
        reasons.append("capability_filtered")

        if self._health_registry is not None:
            channels = filter_channels_by_health(ordered_channels=channels, registry=self._health_registry)
            reasons.append("health_filtered")

        return MessagingCapabilityRouteResult(
            ordered_channels=channels,
            reason_codes=tuple(reasons),
        )
