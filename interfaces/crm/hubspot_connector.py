from __future__ import annotations

from crm.providers.hubspot.hubspot_connector import HubSpotConnector
from interfaces.common.base_connector import BaseConnector
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_maturity import ConnectorMaturity


class HubspotConnector(BaseConnector):
    """Honest legacy-facing HubSpot surface.

    This adapter preserves the simple interface expected by the collapsed
    `interfaces/*` registry while exposing the richer CRM provider through
    `provider_connector`. It does not add new decision logic.
    """

    connector_name = 'hubspot_connector'

    def __init__(self, *, provider_connector: HubSpotConnector | None = None) -> None:
        super().__init__()
        object.__setattr__(self, 'connector_name', 'hubspot_connector')
        self.provider_connector = provider_connector or HubSpotConnector()

    def connector_maturity(self) -> ConnectorMaturity:
        return ConnectorMaturity.PLACEHOLDER

    def connector_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            read=False,
            write=False,
            verify=False,
            dry_run=True,
            idempotent=False,
            metadata={
                'maturity': self.connector_maturity().value,
                'provider': 'hubspot',
                'provider_capabilities': dict(vars(self.provider_connector.capabilities())),
            },
        )


__all__ = ['HubspotConnector']
