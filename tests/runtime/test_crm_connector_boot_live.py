from __future__ import annotations

import pytest

from runtime.bootstrap.crm_connector_boot import build_crm_connector_registry


@pytest.mark.parametrize(
    ('provider_key', 'client_id_env', 'client_secret_env'),
    (
        ('amocrm', 'CRM_AMOCRM_CLIENT_ID', 'CRM_AMOCRM_CLIENT_SECRET'),
        ('bitrix24', 'CRM_BITRIX24_CLIENT_ID', 'CRM_BITRIX24_CLIENT_SECRET'),
        ('hubspot', 'CRM_HUBSPOT_CLIENT_ID', 'CRM_HUBSPOT_CLIENT_SECRET'),
        ('pipedrive', 'CRM_PIPEDRIVE_CLIENT_ID', 'CRM_PIPEDRIVE_CLIENT_SECRET'),
    ),
)
def test_connector_boot_uses_live_connectors_when_env_present(
    monkeypatch,
    provider_key: str,
    client_id_env: str,
    client_secret_env: str,
) -> None:
    monkeypatch.setenv(client_id_env, f'{provider_key}-client')
    monkeypatch.setenv(client_secret_env, f'{provider_key}-secret')
    registry = build_crm_connector_registry()

    connector = registry.get(provider_key)
    assert connector.supports_live_api() is True


def test_connector_boot_assembles_every_canonical_provider() -> None:
    registry = build_crm_connector_registry()

    assert registry.keys() == (
        'amocrm',
        'bitrix24',
        'hubspot',
        'pipedrive',
        'salesforce',
    )
