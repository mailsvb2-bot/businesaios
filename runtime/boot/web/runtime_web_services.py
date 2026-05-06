from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True


from dataclasses import dataclass

from runtime.boot.web.runtime_web_infra import RuntimeWebInfra
from runtime.boot.web.runtime_web_routed_services import RuntimeWebRoutedServices


@dataclass(frozen=True)
class RuntimeWebServices(RuntimeWebInfra):
    routed: RuntimeWebRoutedServices | None = None
