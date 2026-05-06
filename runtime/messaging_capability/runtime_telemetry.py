from __future__ import annotations

from runtime.messaging_capability.runtime_registry import resolve_channel_health_registry
from runtime.messaging_capability.telemetry_updater import MessagingCapabilityTelemetryUpdater


def resolve_capability_telemetry_updater(runtime_obj) -> MessagingCapabilityTelemetryUpdater:
    updater = getattr(runtime_obj, 'messaging_capability_telemetry_updater', None)
    if updater is None:
        updater = MessagingCapabilityTelemetryUpdater(
            registry=resolve_channel_health_registry(runtime_obj),
        )
        try:
            setattr(runtime_obj, 'messaging_capability_telemetry_updater', updater)
        except Exception:
            pass
    return updater
