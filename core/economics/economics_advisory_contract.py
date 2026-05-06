from __future__ import annotations

from typing import Any, Protocol


ECONOMICS_ADVISORY_CONTRACT_VERSION = "EA-CONTRACT-V1"


class EconomicsAdvisoryPort(Protocol):
    def analyze_economics(self, *args: Any, **kwargs: Any) -> Any: ...
