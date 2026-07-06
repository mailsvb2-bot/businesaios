from __future__ import annotations

from dataclasses import dataclass

from runtime.boot.web.runtime_web_infra import RuntimeWebInfra
from runtime.boot.web.runtime_web_routed_services import RuntimeWebRoutedServices

CANON_BOOT_WIRING_ONLY = True

@dataclass(frozen=True)
class RuntimeWebServices(RuntimeWebInfra):
    routed: RuntimeWebRoutedServices | None = None
