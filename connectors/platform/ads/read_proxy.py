from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from interfaces.ads.base import AdsConnector, AdsConnectorError
from interfaces.ads.registry import AdsConnectorRegistry


Json = Dict[str, Any]


@dataclass
class AdsReadProxy:
    """Read-only facade over Ads connectors (lives outside core)."""

    registry: AdsConnectorRegistry

    def get_metrics(self, tenant_id: str, *, platform: str, query: Json) -> Json:
        c: Optional[AdsConnector] = self.registry.get(platform)
        if c is None:
            raise AdsConnectorError(f"ads.connector.not_configured:{platform}")
        return c.get_metrics(tenant_id=tenant_id, query=query)
