from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

import logging
from dataclasses import dataclass
from typing import Any

from runtime.boot.failure_policy import raise_or_log_boot_failure
from runtime.boot.web.runtime_web_bundle import RuntimeWebBundle
from runtime.boot.web.runtime_web_bundle_factory import build_runtime_web_bundle
from runtime.boot.web.runtime_web_routed_services import RuntimeWebRoutedServices

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeWebAttachmentState:
    bundle: RuntimeWebBundle
    settings_gateway: Any = None
    messaging_policy_read_service: Any = None
    messaging_policy_event_store: Any = None
    api_security_owner_bundle: Any = None
    routed: RuntimeWebRoutedServices | None = None


def build_runtime_web_attach_core_attrs(*, state: RuntimeWebAttachmentState) -> dict[str, object]:
    return {
        "web_bundle": state.bundle,
        "settings_gateway": state.settings_gateway,
        "messaging_policy_read_service": state.messaging_policy_read_service,
        "messaging_policy_event_store": state.messaging_policy_event_store,
        "api_security_owner_bundle": state.api_security_owner_bundle,
    }


def build_runtime_web_attach_service_attrs(*, routed) -> dict[str, object]:
    return {
        "messaging_policy_trace_search_service": getattr(routed, "messaging_policy_trace_search_service", None),
        "messaging_policy_dashboard_service": getattr(routed, "messaging_policy_dashboard_service", None),
        "messaging_policy_alert_service": getattr(routed, "messaging_policy_alert_service", None),
        "messaging_policy_alert_subscription_service": getattr(routed, "messaging_policy_alert_subscription_service", None),
        "messaging_policy_alert_notifier_stack": getattr(routed, "messaging_policy_alert_notifier_stack", None),
    }


def build_runtime_web_attach_bundle_attrs(*, routed) -> dict[str, object]:
    return {
        "messaging_preferences_bundle": getattr(routed, "messaging_preferences_bundle", None),
        "alert_subscriptions_bundle": getattr(routed, "alert_subscriptions_bundle", None),
        "messaging_policy_snapshot_bundle": getattr(routed, "messaging_policy_snapshot_bundle", None),
        "messaging_policy_trace_search_bundle": getattr(routed, "messaging_policy_trace_search_bundle", None),
        "messaging_policy_dashboard_bundle": getattr(routed, "messaging_policy_dashboard_bundle", None),
        "messaging_policy_alerts_bundle": getattr(routed, "messaging_policy_alerts_bundle", None),
        "messaging_policy_observability_nav_bundle": getattr(routed, "messaging_policy_observability_nav_bundle", None),
    }




def _resolve_runtime_web_security_owner_bundle(*, runtime_obj, explicit_bundle=None):
    if explicit_bundle is not None:
        return explicit_bundle
    direct_bundle = getattr(runtime_obj, "api_security_owner_bundle", None)
    if direct_bundle is not None:
        return direct_bundle
    runtime_infra = getattr(runtime_obj, "runtime_infra", None)
    if runtime_infra is None:
        return None
    return getattr(runtime_infra, "api_security_owner_bundle", None)

def build_runtime_web_attachment_attrs(*, state: RuntimeWebAttachmentState) -> dict[str, object]:
    attrs = {}
    attrs.update(build_runtime_web_attach_core_attrs(state=state))
    attrs.update(build_runtime_web_attach_service_attrs(routed=state.routed))
    attrs.update(build_runtime_web_attach_bundle_attrs(routed=state.routed))
    return attrs


def iter_runtime_web_targets(*, runtime_obj):
    yield runtime_obj
    effects = getattr(runtime_obj, "_effects", None)
    if effects is not None:
        yield effects


def apply_runtime_web_attachment(*, target, attrs: dict[str, object]) -> None:
    for key, value in attrs.items():
        setattr(target, key, value)


def attach_runtime_web_bundle(*, runtime_obj, project_root, settings_gateway, messaging_policy_read_service=None, messaging_policy_event_store=None, api_security_owner_bundle=None):
    bundle = build_runtime_web_bundle(
        project_root=project_root,
        settings_gateway=settings_gateway,
        messaging_policy_read_service=messaging_policy_read_service,
        messaging_policy_event_store=messaging_policy_event_store,
    )
    state = RuntimeWebAttachmentState(
        bundle=bundle,
        settings_gateway=settings_gateway,
        messaging_policy_read_service=messaging_policy_read_service,
        messaging_policy_event_store=messaging_policy_event_store,
        api_security_owner_bundle=_resolve_runtime_web_security_owner_bundle(runtime_obj=runtime_obj, explicit_bundle=api_security_owner_bundle),
        routed=bundle.routed,
    )
    attrs = build_runtime_web_attachment_attrs(state=state)
    for target in iter_runtime_web_targets(runtime_obj=runtime_obj):
        try:
            apply_runtime_web_attachment(target=target, attrs=attrs)
        except Exception as exc:
            raise_or_log_boot_failure(
                component="runtime_web_attachment",
                exc=exc,
                logger=LOGGER,
            )
            continue
    return bundle


__all__ = [
    "RuntimeWebAttachmentState",
    "build_runtime_web_attach_core_attrs",
    "build_runtime_web_attach_service_attrs",
    "build_runtime_web_attach_bundle_attrs",
    "build_runtime_web_attachment_attrs",
    "iter_runtime_web_targets",
    "apply_runtime_web_attachment",
    "attach_runtime_web_bundle",
]
