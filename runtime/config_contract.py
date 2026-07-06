from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

RUNTIME_CONFIG_CONTRACT_VERSION = "RCC-CONTRACT-V1"

class RuntimeConfigPort(Protocol):
    def load(self) -> Mapping[str, Any]: ...
