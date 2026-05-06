from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from interfaces.ads.base import AdsConnector, AdsConnectorError
from interfaces.ads.registry import AdsConnectorRegistry


Json = Dict[str, Any]


@dataclass
class AdsApplyService:
    """Write/mutation service over Ads connectors (lives outside core)."""

    registry: AdsConnectorRegistry

    def apply(self, tenant_id: str, *, platform: str, plan: Json) -> Json:
        c: Optional[AdsConnector] = self.registry.get(platform)
        if c is None:
            raise AdsConnectorError(f"ads.connector.not_configured:{platform}")
        return c.apply_plan(tenant_id=tenant_id, plan=plan)
