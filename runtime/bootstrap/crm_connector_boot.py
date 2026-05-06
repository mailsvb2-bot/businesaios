from __future__ import annotations

import os

from crm.providers.common.crm_oauth_token_store import (
    InMemoryCrmOAuthTokenStore,
    SecretVaultBackedCrmOAuthTokenStore,
)
from crm.providers.hubspot.hubspot_connector import HubSpotConnector
from crm.providers.pipedrive.pipedrive_connector import PipedriveConnector
from crm.registry.crm_connector_registry import CrmConnectorRegistry
from security.secret_vault import SecretVault, build_default_secret_vault


def build_crm_connector_registry(*, token_store=None, vault: SecretVault | None = None) -> CrmConnectorRegistry:
    active_token_store = token_store or _build_token_store(vault=vault)
    return CrmConnectorRegistry(
        connectors={
            'hubspot': HubSpotConnector(
                token_store=active_token_store,
                client_id=_getenv('CRM_HUBSPOT_CLIENT_ID'),
                client_secret=_getenv('CRM_HUBSPOT_CLIENT_SECRET'),
            ),
            'pipedrive': PipedriveConnector(
                token_store=active_token_store,
                client_id=_getenv('CRM_PIPEDRIVE_CLIENT_ID'),
                client_secret=_getenv('CRM_PIPEDRIVE_CLIENT_SECRET'),
            ),
        }
    )


def _build_token_store(*, vault: SecretVault | None = None):
    if vault is not None or _use_vault_backed_token_store():
        return SecretVaultBackedCrmOAuthTokenStore(vault=vault or build_default_secret_vault())
    return InMemoryCrmOAuthTokenStore()


def _use_vault_backed_token_store() -> bool:
    return _has_live_credentials('CRM_HUBSPOT_CLIENT_ID', 'CRM_HUBSPOT_CLIENT_SECRET') or _has_live_credentials(
        'CRM_PIPEDRIVE_CLIENT_ID', 'CRM_PIPEDRIVE_CLIENT_SECRET'
    )


def _has_live_credentials(client_id_env: str, client_secret_env: str) -> bool:
    return bool(_getenv(client_id_env) and _getenv(client_secret_env))


def _getenv(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if isinstance(value, str) and value.strip() else None
