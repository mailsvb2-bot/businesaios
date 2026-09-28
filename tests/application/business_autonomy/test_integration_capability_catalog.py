import pytest

from application.business_autonomy.integration_capability_catalog import (
    CAPABILITY_SCHEMA_VERSION,
    CapabilityLifecycle,
    CapabilityStatus,
    CapabilitySurface,
    IntegrationCapability,
    capability_map,
    list_integration_capability_payloads,
    summarize_integration_capabilities,
)
from application.business_autonomy.provider_catalog import (
    BRIDGE_MESSAGING_PROVIDER_KEYS,
    MESSAGING_CHANNEL_PROVIDER_KEYS,
    MESSAGING_GUARDED_WRITE_PROVIDER_KEYS,
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
        assert capability.write_supported is (provider_key in MESSAGING_GUARDED_WRITE_PROVIDER_KEYS)
        assert capability.verify_supported is True
        assert capability.connectable is True

    catalog = capability_map()
    assert catalog['interaction.instagram_direct'].provider_keys == ('instagram_messaging',)
    assert catalog['interaction.facebook_messenger'].provider_keys == ('messenger_messaging',)


def test_capability_definitions_are_versioned_and_immutable():
    capability = capability_map()["interaction.telegram"]
    assert capability.schema_version == CAPABILITY_SCHEMA_VERSION == 1
    payload = capability.to_payload()
    assert payload["schema_version"] == 1
    try:
        capability.metadata["forged"] = True
    except TypeError:
        pass
    else:
        raise AssertionError("capability metadata must be immutable")


def test_capability_map_is_a_copy_of_release_catalog_index():
    first = capability_map()
    first.pop("interaction.telegram")
    assert "interaction.telegram" in capability_map()
    assert all(isinstance(item, IntegrationCapability) for item in capability_map().values())


def test_capability_lifecycle_matches_canon_state_set():
    assert {item.value for item in CapabilityLifecycle} == {
        "defined",
        "implemented",
        "integrated",
        "tested",
        "live_verified",
        "user_available",
        "production_ready",
        "degraded",
        "disabled",
        "deprecated",
    }


def test_capability_payload_exposes_canonical_contract_surface():
    payload = capability_map()["interaction.telegram"].to_payload()
    assert payload["lifecycle"] == "implemented"
    assert payload["input_schema"] == {}
    assert payload["output_schema"] == {}
    assert payload["health"] == "unknown"
    assert payload["availability"] == "unknown"
    assert payload["cost"] == 0.0
    assert payload["latency_ms"] == 0.0
    assert payload["reliability"] == 0.0
    assert payload["reversible"] is False
    assert payload["approval_requirements"] == {
        "owner_approval": True,
        "budget_guard": False,
        "consent": False,
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"cost": -0.01}, "cost/latency"),
        ({"latency_ms": -1}, "cost/latency"),
        ({"reliability": -0.01}, "reliability"),
        ({"reliability": 1.01}, "reliability"),
    ],
)
def test_capability_contract_numeric_bounds_fail_closed(kwargs, message):
    with pytest.raises(ValueError, match=message):
        IntegrationCapability(
            capability_id="interaction.test",
            title="Test",
            surface=CapabilitySurface.INTERACTION,
            group="Test",
            status=CapabilityStatus.IMPLEMENTED,
            owner_text="owner",
            next_required_step="next",
            **kwargs,
        )


def test_production_ready_capability_cannot_claim_weaker_lifecycle():
    with pytest.raises(ValueError, match="production_ready lifecycle"):
        IntegrationCapability(
            capability_id="interaction.test",
            title="Test",
            surface=CapabilitySurface.INTERACTION,
            group="Test",
            status=CapabilityStatus.PRODUCTION_READY,
            lifecycle=CapabilityLifecycle.TESTED,
            owner_text="owner",
            next_required_step="next",
        )
