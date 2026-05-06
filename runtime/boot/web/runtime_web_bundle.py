from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True


from runtime.boot.web.runtime_web_observability_boot import (
    boot_runtime_web_bundle_fastapi,
    boot_runtime_web_bundle_flask,
)
from runtime.boot.web.runtime_web_services import RuntimeWebServices


class RuntimeWebBundle:
    def __init__(self, *, services: RuntimeWebServices):
        self._services = services

    @property
    def settings_gateway(self):
        return self._services.settings_gateway

    @property
    def messaging_policy_read_service(self):
        return self._services.messaging_policy_read_service

    @property
    def messaging_policy_event_store(self):
        return self._services.messaging_policy_event_store

    @property
    def routed(self):
        return self._services.routed

    def boot_fastapi(self, *, app) -> None:
        boot_runtime_web_bundle_fastapi(app=app, services=self._services)

    def boot_flask(self, *, app) -> None:
        boot_runtime_web_bundle_flask(app=app, services=self._services)
