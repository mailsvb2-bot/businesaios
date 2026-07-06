from __future__ import annotations

from dataclasses import dataclass

from runtime.boot.web.observability_boot_plan import MessagingPolicyObservabilityBootFlags

CANON_BOOT_WIRING_ONLY = True

@dataclass(frozen=True)
class RuntimeWebFlagState:
    has_settings_gateway: bool
    has_read_service: bool
    has_event_store: bool


def read_runtime_web_flag_state(*, services) -> RuntimeWebFlagState:
    return RuntimeWebFlagState(
        has_settings_gateway=services.settings_store is not None,
        has_read_service=services.messaging_policy_reader is not None,
        has_event_store=services.messaging_policy_store is not None,
    )


def build_runtime_web_default_flags(*, services) -> MessagingPolicyObservabilityBootFlags:
    state = read_runtime_web_flag_state(services=services)
    return MessagingPolicyObservabilityBootFlags(
        navigation=True,
        snapshot=state.has_read_service,
        traces=state.has_event_store,
        dashboard=state.has_event_store,
        alerts=state.has_event_store,
        alert_subscriptions=state.has_settings_gateway,
        messaging_preferences=state.has_settings_gateway,
    )


__all__ = [
    "RuntimeWebFlagState",
    "read_runtime_web_flag_state",
    "build_runtime_web_default_flags",
    "MessagingPolicyObservabilityBootFlags",
]
