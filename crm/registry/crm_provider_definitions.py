from __future__ import annotations

from crm.providers.amocrm.amocrm_capability_descriptor import (
    build_amocrm_capability_descriptor,
)
from crm.providers.amocrm.amocrm_connector import AmoCrmConnector
from crm.providers.bitrix24.bitrix24_capability_descriptor import (
    build_bitrix24_capability_descriptor,
)
from crm.providers.bitrix24.bitrix24_connector import Bitrix24Connector
from crm.providers.hubspot.hubspot_capability_descriptor import (
    build_hubspot_capability_descriptor,
)
from crm.providers.hubspot.hubspot_connector import HubSpotConnector
from crm.providers.pipedrive.pipedrive_capability_descriptor import (
    build_pipedrive_capability_descriptor,
)
from crm.providers.pipedrive.pipedrive_connector import PipedriveConnector
from crm.providers.salesforce.salesforce_capability_descriptor import (
    build_salesforce_capability_descriptor,
)
from crm.providers.salesforce.salesforce_connector import SalesforceConnector
from crm.registry.crm_provider_definition import CrmProviderDefinition


def build_default_crm_provider_definitions() -> tuple[CrmProviderDefinition, ...]:
    """Canonical built-in CRM assembly manifest.

    Additional providers should be supplied as explicit CrmProviderDefinition
    values at the application composition boundary rather than by editing
    decision, workflow, or execution logic.
    """

    return (
        CrmProviderDefinition(
            provider_key='amocrm',
            display_name='amoCRM',
            default_rank=75,
            capability_factory=build_amocrm_capability_descriptor,
            connector_factory=AmoCrmConnector,
        ),
        CrmProviderDefinition(
            provider_key='bitrix24',
            display_name='Bitrix24',
            default_rank=70,
            capability_factory=build_bitrix24_capability_descriptor,
            connector_factory=Bitrix24Connector,
        ),
        CrmProviderDefinition(
            provider_key='hubspot',
            display_name='HubSpot',
            default_rank=90,
            capability_factory=build_hubspot_capability_descriptor,
            connector_factory=HubSpotConnector,
        ),
        CrmProviderDefinition(
            provider_key='salesforce',
            display_name='Salesforce',
            default_rank=85,
            capability_factory=build_salesforce_capability_descriptor,
            connector_factory=SalesforceConnector,
        ),
        CrmProviderDefinition(
            provider_key='pipedrive',
            display_name='Pipedrive',
            default_rank=80,
            capability_factory=build_pipedrive_capability_descriptor,
            connector_factory=PipedriveConnector,
        ),
    )


__all__ = ['build_default_crm_provider_definitions']
