from application.business_autonomy.integration_capability_catalog import (
    CapabilitySurface,
    capability_map,
    list_integration_capability_payloads,
    summarize_integration_capabilities,
)
from application.business_autonomy.provider_catalog import (
    BRIDGE_MESSAGING_PROVIDER_KEYS,
    MESSAGING_CHANNEL_PROVIDER_KEYS,
)


def test_capability_catalog_exposes_honest_statuses():
    capabilities = capability_map()

    assert capabilities['interaction.telegram'].status.value == 'partial'
    assert capabilities['interaction.telegram'].connectable is True
    assert capabilities['acquisition.telegram_ads'].roadmap_only is True
    assert capabilities['acquisition.meta_ads'].connectable is False
    assert capabilities['acquisition.google_ads'].requires_budget_guard is True


def test_capability_payload_blocks_roadmap_as_connectable():
    rows = list_integration_capability_payloads(include_roadmap=True)
    by_id = {row['id']: row for row in rows}

    assert by_id['acquisition.meta_ads']['connectable'] is False
    assert by_id['acquisition.meta_ads']['roadmap_only'] is True
    assert by_id['interaction.email']['connectable'] is True
    assert by_id['interaction.email']['requires_consent'] is True


def test_capability_summary_counts_are_consistent():
    rows = list_integration_capability_payloads(include_roadmap=True)
    summary = summarize_integration_capabilities()

    assert summary['total'] == len(rows)
    assert summary['connectable'] + summary['roadmap_only'] == summary['total']
    assert summary['by_surface']['acquisition'] > 0
    assert summary['by_surface']['interaction'] > 0


def test_every_external_messaging_provider_has_honest_interaction_capability():
    capabilities = tuple(
        capability for capability in capability_map().values()
        if capability.surface is CapabilitySurface.INTERACTION
    )
    by_provider: dict[str, list] = {}
    for capability in capabilities:
        for provider_key in capability.provider_keys:
            by_provider.setdefault(provider_key, []).append(capability)

    assert len(MESSAGING_CHANNEL_PROVIDER_KEYS) == 15
    for channel, provider_key in MESSAGING_CHANNEL_PROVIDER_KEYS.items():
        matches = by_provider.get(provider_key, [])
        assert len(matches) == 1, (channel, provider_key, [item.capability_id for item in matches])

    for provider_key in BRIDGE_MESSAGING_PROVIDER_KEYS:
        capability = by_provider[provider_key][0]
        assert capability.status.value == 'partial'
        assert capability.read_supported is True
        assert capability.write_supported is False
        assert capability.verify_supported is True
        assert capability.connectable is True

    catalog = capability_map()
    assert catalog['interaction.instagram_direct'].provider_keys == ('instagram_messaging',)
    assert catalog['interaction.facebook_messenger'].provider_keys == ('messenger_messaging',)
