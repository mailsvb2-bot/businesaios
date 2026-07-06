from __future__ import annotations

from pathlib import Path

from runtime.boot.web.runtime_web_bundle import RuntimeWebBundle
from runtime.boot.web.runtime_web_service_builders import build_runtime_web_routed_services
from runtime.boot.web.runtime_web_services import RuntimeWebServices

CANON_BOOT_WIRING_ONLY = True

def build_runtime_web_bundle(*, project_root, settings_gateway, messaging_policy_read_service=None, messaging_policy_event_store=None):
    routed = build_runtime_web_routed_services(
        project_root=project_root,
        settings_gateway=settings_gateway,
        messaging_policy_read_service=messaging_policy_read_service,
        messaging_policy_event_store=messaging_policy_event_store,
    )
    services = RuntimeWebServices(
        project_root=Path(project_root),
        settings_gateway=settings_gateway,
        messaging_policy_read_service=messaging_policy_read_service,
        messaging_policy_event_store=messaging_policy_event_store,
        routed=routed,
    )
    return RuntimeWebBundle(services=services)
