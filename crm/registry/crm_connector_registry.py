from __future__ import annotations

from dataclasses import dataclass

from crm.crm_connector_contract import CrmConnector
from crm.providers.hubspot.hubspot_connector import HubSpotConnector
from crm.providers.pipedrive.pipedrive_connector import PipedriveConnector


@dataclass
class CrmConnectorRegistry:
    """Canonical runtime registry for concrete CRM connector instances.

    The provider catalog remains the source of truth for provider capability
    metadata. This registry owns only instantiated adapters so execution,
    onboarding, verification, and state synthesis all reuse the same connector
    objects inside one runtime instead of silently creating isolated stores.
    """

    connectors: dict[str, CrmConnector]

    @classmethod
    def build_default(cls) -> 'CrmConnectorRegistry':
        return cls(
            connectors={
                'hubspot': HubSpotConnector(),
                'pipedrive': PipedriveConnector(),
            }
        )

    def get(self, provider_key: str) -> CrmConnector:
        try:
            return self.connectors[provider_key]
        except KeyError as exc:
            raise LookupError(f'Unknown CRM connector: {provider_key}') from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.connectors))
