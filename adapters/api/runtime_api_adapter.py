from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_API_RUNTIME_ADAPTER_SINGLE_OWNER = True


def build_runtime_api_adapter(*, application_service: object) -> "RuntimeApiAdapter":
    return RuntimeApiAdapter(application_service=application_service)


@dataclass(frozen=True)
class RuntimeApiAdapter:
    application_service: object

    def handle_action(self, action: object) -> dict[str, Any]:
        return self.application_service.execute_action(action)

    def health(self) -> dict[str, Any]:
        startup_audit_events = list(self.application_service.startup_audit_events())
        status = "ready" if not startup_audit_events else "degraded"
        return {
            "status": status,
            "startup_audit_events": startup_audit_events,
        }


__all__ = [
    "CANON_API_RUNTIME_ADAPTER_SINGLE_OWNER",
    "RuntimeApiAdapter",
    "build_runtime_api_adapter",
]
