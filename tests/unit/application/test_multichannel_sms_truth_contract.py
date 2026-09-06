from __future__ import annotations

from application.business_autonomy.integration_capability_catalog import CapabilityStatus, capability_map
from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_truth_matrix import ProviderTruthStatus, provider_truth_map
from application.public_site.cta_intake import public_integration_marketplace
from interfaces.common.connector_maturity import ConnectorMaturity
from interfaces.communications.sms_connector import SmsConnector
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from runtime.business_autonomy.provider_transport_bindings import provider_transport_binding_for_key
from security.secret_vault import InMemorySecretVault


def test_sms_transport_does_not_invent_vendor_endpoint_or_operations() -> None:
    binding = provider_transport_binding_for_key("sms_connector")
    assert binding["auth_scheme"] == "vendor_specific_credentials"
    assert binding["base_url"] == "vendor-configured"
    assert binding["probe_path"] == ""
    assert binding["sync_path_family"] == ""
    assert binding["contract_only"] is True
    assert binding["live_probe_ready"] is False
    assert binding["live_read_ready"] is False
    assert binding["live_write_ready"] is False
    assert binding["live_ready"] is False
    assert "http://" not in repr(binding) and "https://" not in repr(binding)


def test_sms_truth_remains_contract_only_and_fail_closed() -> None:
    row = provider_truth_map()["sms_connector"]
    assert row.status == ProviderTruthStatus.CONTRACT_ONLY.value
    assert row.has_real_endpoint is False
    assert row.has_placeholder_endpoint is True
    assert row.read_only_supported is False
    assert row.write_supported is False
    assert row.live_ready is False
    assert row._live_ready_false_reason() == "placeholder_endpoint"

    capability = capability_map()["interaction.sms"]
    assert capability.status is CapabilityStatus.CONTRACT_ONLY
    assert capability.read_supported is False
    assert capability.write_supported is False
    assert capability.verify_supported is False

    marketplace = {item["provider_key"]: item for item in public_integration_marketplace()}
    sms_marketplace = marketplace["sms_connector"]
    assert sms_marketplace["selectable"] is False
    assert sms_marketplace["connection_mode"] == "vendor_selection_required"
    assert sms_marketplace["credential_labels"] == []

    provider = provider_map()["sms_connector"]
    assert provider.supports_business_onboarding is False
    assert provider.secret_fields == ()

    health = ProviderConnectorHealthService(InMemorySecretVault())
    for mode in ("dry_run", "live"):
        result = health.probe(
            provider=provider,
            tenant_id="tenant-sms-contract",
            business_id="business-sms-contract",
            probe_mode=mode,
        )
        assert result.status == "contract_only"
        assert result.reason == "vendor_contract_not_selected"
        assert result.metadata["live_probe_supported"] is False


def test_sms_connector_stays_placeholder_until_vendor_adapter_exists() -> None:
    connector = SmsConnector()
    assert connector.connector_maturity() is ConnectorMaturity.PLACEHOLDER
    capabilities = connector.connector_capabilities()
    assert capabilities.read is False
    assert capabilities.write is False
    assert capabilities.verify is False
    assert capabilities.dry_run is True
