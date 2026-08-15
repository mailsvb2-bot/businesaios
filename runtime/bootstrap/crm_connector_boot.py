from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import replace

from crm.crm_connector_contract import CrmConnector
from crm.providers.amocrm.amocrm_connector import AmoCrmConnector
from crm.providers.bitrix24.bitrix24_connector import Bitrix24Connector
from crm.providers.common.crm_oauth_token_store import (
    CrmOAuthTokenStore,
    InMemoryCrmOAuthTokenStore,
    SecretVaultBackedCrmOAuthTokenStore,
)
from crm.providers.hubspot.hubspot_connector import HubSpotConnector
from crm.providers.pipedrive.pipedrive_connector import PipedriveConnector
from crm.providers.salesforce.salesforce_connector import SalesforceConnector
from crm.registry.crm_connector_registry import CrmConnectorRegistry
from crm.registry.crm_provider_assembly import CrmProviderAssembly
from crm.registry.crm_provider_definition import CrmProviderDefinition
from crm.registry.crm_provider_definitions import build_default_crm_provider_definitions
from security.secret_vault import SecretVault, build_default_secret_vault

_OAUTH_CLIENT_ENV_PAIRS = (
    ('CRM_AMOCRM_CLIENT_ID', 'CRM_AMOCRM_CLIENT_SECRET'),
    ('CRM_BITRIX24_CLIENT_ID', 'CRM_BITRIX24_CLIENT_SECRET'),
    ('CRM_HUBSPOT_CLIENT_ID', 'CRM_HUBSPOT_CLIENT_SECRET'),
    ('CRM_PIPEDRIVE_CLIENT_ID', 'CRM_PIPEDRIVE_CLIENT_SECRET'),
)


def build_crm_connector_registry(
    *,
    token_store: CrmOAuthTokenStore | None = None,
    vault: SecretVault | None = None,
) -> CrmConnectorRegistry:
    """Build runtime connectors from the canonical provider-definition manifest.

    The CRM provider definitions remain the single source of provider identity,
    capability metadata, enablement and connector ownership. This composition
    layer only injects deployment secrets/token storage into those factories.
    """

    active_token_store = (
        token_store if token_store is not None else _build_token_store(vault=vault)
    )
    definitions = tuple(
        _with_runtime_dependencies(definition, token_store=active_token_store)
        for definition in build_default_crm_provider_definitions()
    )
    return CrmProviderAssembly.from_definitions(definitions).build_connector_registry()


def _with_runtime_dependencies(
    definition: CrmProviderDefinition,
    *,
    token_store: CrmOAuthTokenStore,
) -> CrmProviderDefinition:
    connector_factory = _runtime_connector_factory(
        definition.provider_key,
        token_store=token_store,
    )
    if connector_factory is None:
        return definition
    return replace(definition, connector_factory=connector_factory)


def _runtime_connector_factory(
    provider_key: str,
    *,
    token_store: CrmOAuthTokenStore,
) -> Callable[[], CrmConnector] | None:
    if provider_key == 'amocrm':
        return lambda: AmoCrmConnector(
            token_store=token_store,
            client_id=_getenv('CRM_AMOCRM_CLIENT_ID'),
            client_secret=_getenv('CRM_AMOCRM_CLIENT_SECRET'),
        )
    if provider_key == 'bitrix24':
        return lambda: Bitrix24Connector(
            token_store=token_store,
            client_id=_getenv('CRM_BITRIX24_CLIENT_ID'),
            client_secret=_getenv('CRM_BITRIX24_CLIENT_SECRET'),
        )
    if provider_key == 'hubspot':
        return lambda: HubSpotConnector(
            token_store=token_store,
            client_id=_getenv('CRM_HUBSPOT_CLIENT_ID'),
            client_secret=_getenv('CRM_HUBSPOT_CLIENT_SECRET'),
        )
    if provider_key == 'pipedrive':
        return lambda: PipedriveConnector(
            token_store=token_store,
            client_id=_getenv('CRM_PIPEDRIVE_CLIENT_ID'),
            client_secret=_getenv('CRM_PIPEDRIVE_CLIENT_SECRET'),
        )
    if provider_key == 'salesforce':
        return lambda: SalesforceConnector(token_store=token_store)
    return None


def _build_token_store(*, vault: SecretVault | None = None) -> CrmOAuthTokenStore:
    if vault is not None or _use_vault_backed_token_store():
        return SecretVaultBackedCrmOAuthTokenStore(
            vault=vault or build_default_secret_vault()
        )
    return InMemoryCrmOAuthTokenStore()


def _use_vault_backed_token_store() -> bool:
    return any(
        _has_live_credentials(client_id_env, client_secret_env)
        for client_id_env, client_secret_env in _OAUTH_CLIENT_ENV_PAIRS
    )


def _has_live_credentials(client_id_env: str, client_secret_env: str) -> bool:
    return bool(_getenv(client_id_env) and _getenv(client_secret_env))


def _getenv(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if isinstance(value, str) and value.strip() else None
