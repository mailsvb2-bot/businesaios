from __future__ import annotations

from pathlib import Path

from application.business_autonomy.integration_capability_catalog import (
    CANON_CAPABILITY_ENTITY_OWNER,
    CAPABILITIES,
    CAPABILITY_SCHEMA_VERSION,
    IntegrationCapability,
    capability_map,
)
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("application/business_autonomy/integration_capability_catalog.py")
PRODUCTION_ROOTS = ("application", "runtime", "core", "contracts", "execution", "interfaces")


def _owner_marker_files() -> list[Path]:
    owners: list[Path] = []
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "CANON_CAPABILITY_ENTITY_OWNER = True" in path.read_text(encoding="utf-8"):
                owners.append(path.relative_to(ROOT))
    return sorted(owners)


def test_capability_inventory_names_release_managed_definition_owner() -> None:
    row = ontology_ownership_by_entity()["Capability"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "application.business_autonomy.integration_capability_catalog"
    assert row.storage_owner == "application.business_autonomy.integration_capability_catalog"
    assert row.allowed_writers == ("application.business_autonomy.integration_capability_catalog",)
    assert row.allowed_readers == (
        "application.business_autonomy.provider_truth_matrix",
        "application.public_site.landing_content",
    )


def test_capability_entity_owner_marker_is_unique() -> None:
    assert CANON_CAPABILITY_ENTITY_OWNER is True
    assert IntegrationCapability.__module__ == "application.business_autonomy.integration_capability_catalog"
    assert _owner_marker_files() == [OWNER]


def test_release_catalog_ids_and_schema_are_unique_and_surface_bound() -> None:
    assert CAPABILITY_SCHEMA_VERSION == 1
    ids = tuple(item.capability_id for item in CAPABILITIES)
    assert len(ids) == len(set(ids))
    assert capability_map().keys() == set(ids)
    for item in CAPABILITIES:
        assert item.schema_version == CAPABILITY_SCHEMA_VERSION
        assert item.capability_id.startswith(f"{item.surface.value}.")


def test_scoped_capability_surfaces_do_not_claim_entity_ownership() -> None:
    scoped = (
        ROOT / "application/business_autonomy/contracts.py",
        ROOT / "application/capability/capability_matrix.py",
        ROOT / "execution/routing/capability_registry.py",
        ROOT / "runtime/capability/model.py",
        ROOT / "core/decisioning/capability_vocabulary.py",
    )
    for path in scoped:
        text = path.read_text(encoding="utf-8")
        assert "CANON_CAPABILITY_ENTITY_OWNER" not in text


def test_runtime_business_enablement_stays_with_business_registry() -> None:
    distributed = (ROOT / "application/business_autonomy/distributed_capability_trust_registry.py").read_text(encoding="utf-8")
    assert "capabilities: tuple[BusinessCapability, ...]" in distributed
    assert '"capabilities": [' in distributed
    assert "def capability_snapshot(" in distributed
