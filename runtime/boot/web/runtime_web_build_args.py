from __future__ import annotations

from dataclasses import dataclass

from runtime.boot.web.runtime_web_infra import RuntimeWebInfra

CANON_BOOT_WIRING_ONLY = True

@dataclass(frozen=True)
class RuntimeWebBuildArgs(RuntimeWebInfra):
    pass
