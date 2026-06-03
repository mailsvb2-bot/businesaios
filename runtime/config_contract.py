from __future__ import annotations

from typing import Any, Protocol
from collections.abc import Mapping

RUNTIME_CONFIG_CONTRACT_VERSION = "RCC-CONTRACT-V1"

class RuntimeConfigPort(Protocol):
    def load(self) -> Mapping[str, Any]: ...
