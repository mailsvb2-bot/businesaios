from __future__ import annotations

"""Read-only demo ads connector. Production must use a real provider (Meta/Yandex/VK/Telegram Ads)."""

from datetime import date
from typing import AsyncIterator, Optional, Sequence

from interfaces.ads.base import AdsConnector
from interfaces.ads.capabilities import AdsCapabilities
from interfaces.ads.contracts import (
    Campaign,
    CreateOrUpdateRequest,
    CreateOrUpdateResponse,
    MetricsPoint,
    OAuthConnectRequest,
    OAuthConnectResult,
)
from interfaces.ads.errors import ValidationError
from interfaces.ads.connector_availability_guard import build_demo_connector_metadata, build_demo_write_error

# Explicit marker: this is NOT a production integration.
READ_ONLY_DEMO_CONNECTOR = True


class ReadOnlyDemoConnector(AdsConnector):
    """Safe read-only demo connector. Replace with real provider integrations."""

    def __init__(self, platform: str):
        self._platform = platform

    @property
    def platform(self) -> str:
        return self._platform

    def capabilities(self) -> AdsCapabilities:
        return AdsCapabilities(read_inventory=True, read_metrics=True, write_campaigns=False, write_budgets=False)

    async def connect(self, req: OAuthConnectRequest) -> OAuthConnectResult:
        if not req.redirect_uri or not req.state:
            raise ValidationError("redirect_uri and state required", field="redirect_uri/state", platform=self.platform)
        return OAuthConnectResult(
            authorization_url=f"https://example.invalid/oauth/{self.platform}?state={req.state}",
            raw=build_demo_connector_metadata(platform=self.platform),
        )

    async def list_campaigns(self, *, tenant_id: str, account_id: str) -> Sequence[Campaign]:
        return []

    async def fetch_metrics(
        self,
        *,
        tenant_id: str,
        account_id: str,
        level: str,
        object_ids: Optional[Sequence[str]],
        date_from: date,
        date_to: date,
    ) -> AsyncIterator[MetricsPoint]:
        if date_to < date_from:
            raise ValidationError("date_to < date_from", field="date_to", platform=self.platform)
        if False:
            yield

    async def create_or_update(
        self,
        *,
        tenant_id: str,
        account_id: str,
        req: CreateOrUpdateRequest,
    ) -> CreateOrUpdateResponse:
        return CreateOrUpdateResponse(ok=False, raw=build_demo_write_error(platform=self.platform))

# Historical alias kept temporarily for import stability inside this archive.
ReadOnlyDemoConnector = ReadOnlyDemoConnector

__all__ = ["READ_ONLY_DEMO_CONNECTOR", "ReadOnlyDemoConnector", "ReadOnlyDemoConnector"]
