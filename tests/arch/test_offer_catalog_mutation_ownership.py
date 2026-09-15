from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNER = ROOT / "runtime" / "_internal" / "offer_catalog_mutation.py"
PRICING = ROOT / "runtime" / "_internal" / "effects_domains" / "admin_pricing.py"
PATCH = ROOT / "runtime" / "_internal" / "effects_actions" / "offer_patch_actions.py"


def test_offer_catalog_has_one_durable_mutation_owner() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    pricing = PRICING.read_text(encoding="utf-8")
    patch = PATCH.read_text(encoding="utf-8")

    assert "CANON_OFFER_CATALOG_MUTATION_OWNER = True" in owner
    assert "from runtime._internal.offer_catalog_mutation import" in pricing
    assert "from runtime._internal.offer_catalog_mutation import" in patch
    assert "CatalogMutationTransaction" in owner
    assert "acquire_catalog_lock" in owner


def test_effect_layers_do_not_own_catalog_file_replacement_mechanics() -> None:
    for path in (PRICING, PATCH):
        text = path.read_text(encoding="utf-8")
        assert "fcntl" not in text
        assert "threading.Lock" not in text
        assert "invalidate_yaml_cache" not in text
        assert ".replace(self.catalog_path)" not in text
        assert ".write_text(" not in text


def test_offer_inventory_records_single_storage_owner_without_overclaiming_done() -> None:
    from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity

    row = ontology_ownership_by_entity()["Offer"]
    assert row.status is OwnershipAuditStatus.PARTIAL
    assert row.storage_owner == "runtime._internal.offer_catalog_mutation"
    assert set(row.allowed_writers) == {
        "runtime._internal.effects_domains.admin_pricing",
        "runtime._internal.effects_actions.offer_patch_actions",
    }
    assert "Semantic Offer shapes" in row.reason
