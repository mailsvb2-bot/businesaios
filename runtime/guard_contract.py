from __future__ import annotations

from typing import Any, Protocol

RUNTIME_GUARD_CONTRACT_VERSION = "RGC-CONTRACT-V1"

class RuntimeGuardPort(Protocol):
    def validate(self, *, action: str, payload: dict[str, Any]) -> None: ...
