from __future__ import annotations

from runtime.bootstrap.crm_connector_boot import build_crm_connector_registry


def test_connector_boot_uses_live_connectors_when_env_present(monkeypatch) -> None:
    monkeypatch.setenv('CRM_HUBSPOT_CLIENT_ID', 'hubspot-client')
    monkeypatch.setenv('CRM_HUBSPOT_CLIENT_SECRET', 'hubspot-secret')
    registry = build_crm_connector_registry()

    connector = registry.get('hubspot')
    assert connector.supports_live_api() is True
