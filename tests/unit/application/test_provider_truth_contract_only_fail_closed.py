from __future__ import annotations

from application.business_autonomy.integration_capability_catalog import CapabilityStatus, capability_map
from application.business_autonomy.provider_truth_matrix import ProviderTruthStatus, provider_truth_map
from application.public_site.cta_intake import public_integration_marketplace


def test_contract_only_provider_never_becomes_customer_selectable_from_runtime_plan_alone() -> None:
    truth = provider_truth_map()
    contract_only = {key for key, row in truth.items() if row.status == ProviderTruthStatus.CONTRACT_ONLY.value}
    assert contract_only
    assert all(truth[key].read_only_supported is False for key in contract_only)

    marketplace = {row['provider_key']: row for row in public_integration_marketplace()}
    for key in contract_only & marketplace.keys():
        assert marketplace[key]['selectable'] is False
        assert marketplace[key]['read_supported'] is False


def test_certified_whatsapp_plain_text_write_stays_guarded_and_partial() -> None:
    capability = capability_map()['interaction.whatsapp']
    truth = provider_truth_map()['whatsapp_cloud']

    assert capability.status is CapabilityStatus.PARTIAL
    assert capability.read_supported is True
    assert capability.verify_supported is True
    assert capability.requires_webhook is True
    assert capability.write_supported is True
    assert capability.requires_owner_approval is True
    assert capability.requires_consent is True
    assert capability.production_ready is False

    assert truth.status == ProviderTruthStatus.PARTIAL.value
    assert truth.write_supported is True
    assert truth.approval_required is True
    assert truth.live_ready is False
    assert truth.write_capabilities == ('message_send',)
    assert 'template_send' not in truth.write_capabilities
