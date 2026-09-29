import pytest

from application.business_autonomy.integration_capability_catalog import (
    CAPABILITY_SCHEMA_VERSION,
    CapabilityAvailabilityState,
    CapabilityEvidence,
    CapabilityHealthState,
    CapabilityLifecycle,
    CapabilityStatus,
    CapabilitySurface,
    IntegrationCapability,
    capability_discovery_snapshot,
    capability_map,
    list_integration_capability_payloads,
    summarize_integration_capabilities,
)
from application.business_autonomy.provider_catalog import (
    BRIDGE_MESSAGING_PROVIDER_KEYS,
    MESSAGING_CHANNEL_PROVIDER_KEYS,
    MESSAGING_GUARDED_WRITE_PROVIDER_KEYS,
)
from application.business_autonomy.provider_runtime_contract import provider_sync_run_result_schema
from contracts.email_outbound import EmailOutboundPayloadV1, email_outbound_payload_schema_v1


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
    assert capability.schema_version == CAPABILITY_SCHEMA_VERSION == 3
    payload = capability.to_payload()
    assert payload["schema_version"] == 3
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
    assert payload["cost"] is None
    assert payload["latency_ms"] is None
    assert payload["reliability"] is None
    assert payload["error_rate"] is None
    assert payload["reversible"] is False
    assert payload["contract_complete"] is False
    assert set(payload["contract_gaps"]) == {"input_schema", "output_schema", "health", "availability", "cost", "latency_ms", "reliability", "error_rate"}
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
        ({"cost": True}, "must not use booleans"),
        ({"latency_ms": False}, "must not use booleans"),
        ({"reliability": True}, "must not use booleans"),
        ({"cost": float("nan")}, "finite numbers"),
        ({"latency_ms": float("inf")}, "finite numbers"),
        ({"reliability": float("-inf")}, "finite numbers"),
        ({"cost": "not-a-number"}, "finite numbers"),
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


def test_connectable_capability_without_provider_is_reported_incomplete():
    capability = IntegrationCapability(
        capability_id="interaction.internal_test",
        title="Internal Test",
        surface=CapabilitySurface.INTERACTION,
        group="Test",
        status=CapabilityStatus.IMPLEMENTED,
        owner_text="owner",
        next_required_step="next",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        health="healthy",
        availability="available",
    )
    assert capability.contract_complete is False
    assert set(capability.contract_gaps) == {"cost", "latency_ms", "reliability", "error_rate", "providers"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("health", "magical"),
        ("availability", "sometimes"),
    ],
)
def test_capability_truth_states_fail_closed(field, value):
    kwargs = {field: value}
    with pytest.raises(ValueError):
        IntegrationCapability(
            capability_id="interaction.invalid_truth",
            title="Invalid Truth",
            surface=CapabilitySurface.INTERACTION,
            group="Test",
            status=CapabilityStatus.CONTRACT_ONLY,
            owner_text="owner",
            next_required_step="next",
            **kwargs,
        )


def test_capability_truth_state_enums_are_explicit():
    assert {item.value for item in CapabilityHealthState} == {
        "unknown", "healthy", "degraded", "unhealthy", "disabled"
    }
    assert {item.value for item in CapabilityAvailabilityState} == {
        "unknown", "available", "degraded", "unavailable"
    }


def test_capability_discovery_overlays_live_provider_truth_without_mutating_catalog():
    static = capability_map()["interaction.telegram"]
    assert static.health is CapabilityHealthState.UNKNOWN
    assert static.availability is CapabilityAvailabilityState.UNKNOWN

    rows = capability_discovery_snapshot(provider_runtime_truth={
        "telegram_bot": {
            "provider_key": "telegram_bot",
            "provider_version": 3,
            "connected": True,
            "onboarding_ready": True,
            "governance_enabled": True,
            "health_probe": {"status": "probe_live_ok", "probe_mode": "live", "reason": "ok"},
            "source": "event_spine.provider_activation",
        }
    })
    telegram = {row["capability_id"]: row for row in rows}["interaction.telegram"]

    assert telegram["health"] == "healthy"
    assert telegram["availability"] == "available"
    assert telegram["provider_runtime"][0]["provider_version"] == 3
    assert "health" not in telegram["contract_gaps"]
    assert "availability" not in telegram["contract_gaps"]
    assert set(telegram["contract_gaps"]) == {"input_schema", "output_schema", "cost", "latency_ms", "reliability", "error_rate"}


def test_dry_run_provider_truth_never_claims_live_health():
    rows = capability_discovery_snapshot(provider_runtime_truth={
        "telegram_bot": {
            "provider_key": "telegram_bot",
            "provider_version": 1,
            "connected": True,
            "onboarding_ready": True,
            "health_probe": {"status": "ready_for_credentials", "probe_mode": "dry_run"},
        }
    })
    telegram = {row["capability_id"]: row for row in rows}["interaction.telegram"]
    assert telegram["availability"] == "available"
    assert telegram["health"] == "unknown"
    assert "health" in telegram["contract_gaps"]

def test_connected_provider_cannot_promote_roadmap_capability_to_live_truth():
    static = capability_map()["acquisition.meta_ads"]
    assert static.status is CapabilityStatus.CONTRACT_ONLY
    assert static.connectable is False

    rows = capability_discovery_snapshot(provider_runtime_truth={
        "meta_ads": {
            "provider_key": "meta_ads",
            "provider_version": 4,
            "connected": True,
            "onboarding_ready": True,
            "governance_enabled": True,
            "health_probe": {
                "status": "probe_live_ok",
                "probe_mode": "live",
                "reason": "provider_credentials_are_valid",
            },
            "source": "event_spine.provider_activation",
        }
    })
    meta_ads = {row["capability_id"]: row for row in rows}["acquisition.meta_ads"]

    assert meta_ads["status"] == "contract_only"
    assert meta_ads["availability"] == "unavailable"
    assert meta_ads["health"] == "unknown"
    assert "availability" not in meta_ads["contract_gaps"]
    assert "health" in meta_ads["contract_gaps"]
    assert meta_ads["contract_complete"] is False

@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), float("-inf"), "bad"])
def test_capability_evidence_confidence_rejects_non_finite_and_non_numeric_truth(value):
    with pytest.raises(ValueError, match="finite number"):
        CapabilityEvidence(source="test", claim="claim", confidence=value)


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_capability_evidence_confidence_rejects_out_of_range_truth(value):
    with pytest.raises(ValueError, match="between 0 and 1"):
        CapabilityEvidence(source="test", claim="claim", confidence=value)


def test_capability_risk_level_reuses_canonical_risk_vocabulary():
    capability = IntegrationCapability(
        capability_id="interaction.risk_test",
        title="Risk Test",
        surface=CapabilitySurface.INTERACTION,
        group="Test",
        status=CapabilityStatus.CONTRACT_ONLY,
        owner_text="owner",
        next_required_step="next",
        risk_level="critical",
    )
    assert capability.risk_level == "critical"
    with pytest.raises(ValueError):
        IntegrationCapability(
            capability_id="interaction.invalid_risk",
            title="Invalid Risk",
            surface=CapabilitySurface.INTERACTION,
            group="Test",
            status=CapabilityStatus.CONTRACT_ONLY,
            owner_text="owner",
            next_required_step="next",
            risk_level="magical",
        )

def test_email_capability_schema_reuses_canonical_outbound_and_runtime_contract_shape():
    email = capability_map()["interaction.email"]
    assert "contracts.email_outbound" in email.registry_sources
    assert "application.business_autonomy.provider_runtime_contract" in email.registry_sources
    assert email.input_schema["required"] == ["recipient", "subject", "body"]
    assert email.input_schema["properties"]["recipient"]["format"] == "email"
    assert email.input_schema["properties"]["subject"]["maxLength"] == 240
    assert email.input_schema["properties"]["body"]["maxLength"] == 100000
    assert email.input_schema["additionalProperties"] is False
    assert email.output_schema["required"] == [
        "provider_key", "operation", "mode", "status", "accepted", "metadata"
    ]
    assert email.output_schema["properties"]["accepted"] == {"type": "boolean"}
    assert set(email.contract_gaps) == {"health", "availability", "cost", "latency_ms", "reliability", "error_rate"}

def test_unknown_numeric_capability_truth_is_explicit_and_not_zero():
    capability = IntegrationCapability(
        capability_id="interaction.unknown_numeric_truth",
        title="Unknown Numeric Truth",
        surface=CapabilitySurface.INTERACTION,
        group="Test",
        status=CapabilityStatus.CONTRACT_ONLY,
        owner_text="owner",
        next_required_step="next",
    )
    payload = capability.to_payload()
    assert payload["cost"] is None
    assert payload["latency_ms"] is None
    assert payload["reliability"] is None
    assert {"cost", "latency_ms", "reliability", "error_rate"} <= set(payload["contract_gaps"])


def test_measured_numeric_capability_truth_closes_only_its_own_gaps():
    capability = IntegrationCapability(
        capability_id="interaction.measured_numeric_truth",
        title="Measured Numeric Truth",
        surface=CapabilitySurface.INTERACTION,
        group="Test",
        status=CapabilityStatus.CONTRACT_ONLY,
        owner_text="owner",
        next_required_step="next",
        cost=0.0,
        latency_ms=0.0,
        reliability=1.0,
        error_rate=0.0,
    )
    assert "cost" not in capability.contract_gaps
    assert "latency_ms" not in capability.contract_gaps
    assert "reliability" not in capability.contract_gaps
    assert "error_rate" not in capability.contract_gaps



def test_capability_discovery_uses_provider_scoped_runtime_metrics_without_cross_provider_mix():
    rows = capability_discovery_snapshot(
        provider_runtime_truth={
            'telegram_bot': {'provider_key': 'telegram_bot', 'connected': True, 'onboarding_ready': True, 'health_probe': {'status': 'probe_live_ok'}},
        },
        provider_metrics_truth={
            'telegram_bot': {'provider_key': 'telegram_bot', 'reliability': 0.75, 'error_rate': 0.25, 'latency_ms': 240.0, 'sample_count': 4},
            'whatsapp_cloud': {'provider_key': 'whatsapp_cloud', 'reliability': 1.0, 'error_rate': 0.0, 'latency_ms': 999.0, 'sample_count': 99},
        },
    )
    telegram = {row['capability_id']: row for row in rows}['interaction.telegram']
    assert telegram['reliability'] == 0.75
    assert telegram['latency_ms'] == 240.0
    assert telegram['error_rate'] == 0.25
    assert telegram['provider_metrics'][0]['provider_key'] == 'telegram_bot'
    assert 'reliability' not in telegram['contract_gaps']
    assert 'latency_ms' not in telegram['contract_gaps']
    assert 'error_rate' not in telegram['contract_gaps']
    assert 'cost' in telegram['contract_gaps']

@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_capability_error_rate_rejects_out_of_range_truth(value):
    with pytest.raises(ValueError, match="error_rate"):
        IntegrationCapability(
            capability_id="interaction.invalid_error_rate",
            title="Invalid Error Rate",
            surface=CapabilitySurface.INTERACTION,
            group="Test",
            status=CapabilityStatus.CONTRACT_ONLY,
            owner_text="owner",
            next_required_step="next",
            error_rate=value,
        )

def test_email_capability_schema_is_owned_by_canonical_contracts():
    email = capability_map()["interaction.email"]
    assert dict(email.input_schema) == email_outbound_payload_schema_v1()
    assert dict(email.output_schema) == provider_sync_run_result_schema()
    normalized = EmailOutboundPayloadV1(
        recipient="Owner <OWNER@example.com>",
        subject="  Hello   world  ",
        body=" message ",
    )
    assert normalized.recipient == "owner@example.com"
    assert normalized.subject == "Hello world"
    assert normalized.body == "message"

def test_production_ready_capability_requires_complete_contract_truth():
    with pytest.raises(ValueError, match="contract gaps"):
        IntegrationCapability(
            capability_id="interaction.not_really_ready",
            title="Not Really Ready",
            surface=CapabilitySurface.INTERACTION,
            group="Test",
            status=CapabilityStatus.PRODUCTION_READY,
            lifecycle=CapabilityLifecycle.PRODUCTION_READY,
            owner_text="owner",
            next_required_step="next",
            provider_keys=("telegram_bot",),
        )


def test_production_ready_capability_accepts_only_complete_contract_truth():
    capability = IntegrationCapability(
        capability_id="interaction.really_ready",
        title="Really Ready",
        surface=CapabilitySurface.INTERACTION,
        group="Test",
        status=CapabilityStatus.PRODUCTION_READY,
        lifecycle=CapabilityLifecycle.PRODUCTION_READY,
        owner_text="owner",
        next_required_step="next",
        provider_keys=("telegram_bot",),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        health=CapabilityHealthState.HEALTHY,
        availability=CapabilityAvailabilityState.AVAILABLE,
        cost=0.0,
        latency_ms=1.0,
        reliability=1.0,
        error_rate=0.0,
    )
    assert capability.contract_complete is True

