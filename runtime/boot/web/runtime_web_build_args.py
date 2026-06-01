from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from dataclasses import dataclass

from runtime.boot.web.runtime_web_infra import RuntimeWebInfra


@dataclass(frozen=True)
class RuntimeWebBuildArgs(RuntimeWebInfra):
    pass
