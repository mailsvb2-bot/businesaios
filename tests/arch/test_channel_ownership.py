from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "application" / "business_autonomy" / "distributed_capability_trust_registry.py"
ONBOARDING = ROOT / "application" / "business_autonomy" / "business_connector_framework.py"
BOOTSTRAP = ROOT / "runtime" / "business_autonomy" / "bootstrap.py"


def test_channel_identity_is_durable_in_canonical_business_registry() -> None:
    registry = REGISTRY.read_text(encoding="utf-8")
    onboarding = ONBOARDING.read_text(encoding="utf-8")

    assert '"channel_adapter_key"' in registry
    assert '"channel_external_ref"' in registry
    assert "def channel_identity_snapshot" in registry
    assert "channel_adapter_key=identity.adapter_key" in onboarding
    assert "channel_external_ref=identity.external_ref" in onboarding


def test_bootstrap_prefers_durable_channel_identity_over_defaults() -> None:
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")

    durable = bootstrap.index("distributed_registry.channel_identity_snapshot")
    legacy = bootstrap.index("_channel_defaults_for(scoped_business_id)", durable)
    assert durable < legacy
    assert "channel_identity_source': 'legacy_default'" in bootstrap


def test_channel_inventory_declares_existing_registry_as_single_owner() -> None:
    from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity

    row = ontology_ownership_by_entity()["Channel"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "application.business_autonomy.channel_contracts"
    assert row.storage_owner == "application.business_autonomy.distributed_capability_trust_registry"
