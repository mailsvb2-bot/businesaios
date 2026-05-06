from __future__ import annotations

from typing import Any, Protocol

ADS_ROUTE_CONTRACT_VERSION = "ARC-CONTRACT-V1"

class StrictAdsRoutePort(Protocol):
    def extract(self, *, payload: dict[str, Any], env: Any) -> Any: ...
