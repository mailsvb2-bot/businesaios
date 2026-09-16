from __future__ import annotations

import ast
from pathlib import Path

import pytest

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts import business_offer, marketplace_offer
from contracts.product_contract import Offer, ProductOffer
from core.offers import offer_types
from core.offers.catalogs import retention_catalog

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "bootstrap", "core", "interfaces", "products", "runtime")
LEGACY_IMPORTS = ("contracts.business_offer", "contracts.marketplace_offer")


def test_product_offer_is_the_canonical_offer_type_and_old_name_is_compat_alias() -> None:
    assert Offer is ProductOffer
    assert retention_catalog.Offer is retention_catalog.LegacyRetentionOffer
    assert business_offer.LEGACY_SPECIALIZED_OFFER_CONTRACT is True
    assert marketplace_offer.LEGACY_SPECIALIZED_OFFER_CONTRACT is True
    assert offer_types.CANON_OFFER_RUNTIME_PROJECTIONS is True


@pytest.mark.parametrize(
    "kwargs",
    (
        {"price_minor": True},
        {"price_minor": 1.5},
        {"price_minor": "100"},
        {"currency": "RU"},
        {"currency": "RUBLE"},
        {"period_days": 0},
        {"period_days": True},
    ),
)
def test_product_offer_validation_is_fail_closed(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "offer_id": "offer-1",
        "title": "Offer 1",
        "price_minor": 100,
        "currency": "RUB",
        "period_days": None,
    }
    values.update(kwargs)
    with pytest.raises(ValueError):
        ProductOffer(**values).validate()


def test_legacy_specialized_offer_contracts_have_no_production_importers() -> None:
    offenders: list[str] = []
    for root_name in PRODUCTION_ROOTS:
        for path in (ROOT / root_name).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if any(module in text for module in LEGACY_IMPORTS):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_no_second_generic_offer_class_remains_in_canonical_offer_files() -> None:
    product_tree = ast.parse((ROOT / "contracts" / "product_contract.py").read_text(encoding="utf-8"))
    retention_tree = ast.parse(
        (ROOT / "core" / "offers" / "catalogs" / "retention_catalog.py").read_text(encoding="utf-8")
    )
    assert [node.name for node in product_tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductOffer"] == [
        "ProductOffer"
    ]
    assert not any(isinstance(node, ast.ClassDef) and node.name == "Offer" for node in product_tree.body)
    assert not any(isinstance(node, ast.ClassDef) and node.name == "Offer" for node in retention_tree.body)


def test_offer_inventory_is_done_with_single_semantic_and_storage_owners() -> None:
    row = ontology_ownership_by_entity()["Offer"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "contracts.product_contract"
    assert row.storage_owner == "runtime._internal.offer_catalog_mutation"
    assert row.allowed_writers == (
        "runtime._internal.effects_domains.admin_pricing",
        "runtime._internal.effects_actions.offer_patch_actions",
    )
    assert row.allowed_readers == (
        "core.offers.offer_catalog_resolver",
        "products.offer_catalog_resolver",
    )
