from __future__ import annotations

from runtime.boot.web.boot_observability import (
    boot_messaging_policy_observability_fastapi,
    boot_messaging_policy_observability_flask,
)
from runtime.boot.web.runtime_web_default_flags import build_runtime_web_default_flags

CANON_BOOT_WIRING_ONLY = True

def boot_runtime_web_bundle_fastapi(*, app, services) -> None:
    boot_messaging_policy_observability_fastapi(
        app=app,
        project_root=services.project_root,
        settings_gateway=services.settings_store,
        messaging_policy_event_store=services.messaging_policy_store,
        messaging_policy_read_service=services.messaging_policy_reader,
        flags=build_runtime_web_default_flags(services=services),
    )


def boot_runtime_web_bundle_flask(*, app, services) -> None:
    boot_messaging_policy_observability_flask(
        app=app,
        project_root=services.project_root,
        settings_gateway=services.settings_store,
        messaging_policy_event_store=services.messaging_policy_store,
        messaging_policy_read_service=services.messaging_policy_reader,
        flags=build_runtime_web_default_flags(services=services),
    )
