from __future__ import annotations

import importlib.util

from canon.business_ontology_inventory import (
    BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT,
    REQUIRED_BUSINESS_ONTOLOGY,
    OwnershipAuditStatus,
    ontology_ownership_by_entity,
)


def test_business_ontology_inventory_covers_every_canon_entity_once() -> None:
    rows = BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT
    assert tuple(row.entity for row in rows) == REQUIRED_BUSINESS_ONTOLOGY
    assert len({row.entity for row in rows}) == len(REQUIRED_BUSINESS_ONTOLOGY)
    assert ontology_ownership_by_entity() == {row.entity: row for row in rows}


def test_resolved_ownership_rows_reference_real_modules_and_unresolved_rows_are_explicit() -> None:
    for row in BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT:
        if row.authoritative_module:
            assert importlib.util.find_spec(row.authoritative_module) is not None, row
        if row.status in {OwnershipAuditStatus.MISSING, OwnershipAuditStatus.DUPLICATE}:
            assert row.reason
        if row.status is OwnershipAuditStatus.DONE:
            assert row.authoritative_module
            assert row.storage_owner
            assert row.allowed_writers
            assert row.allowed_readers
            assert row.reason


def test_done_storage_and_reader_writer_modules_are_real() -> None:
    for row in BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT:
        if row.status is not OwnershipAuditStatus.DONE:
            continue
        assert importlib.util.find_spec(row.storage_owner) is not None, row
        for module in (*row.allowed_writers, *row.allowed_readers):
            assert importlib.util.find_spec(module) is not None, (row, module)


def test_inventory_never_claims_unresolved_entity_has_authoritative_owner() -> None:
    for row in BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT:
        if row.status in {OwnershipAuditStatus.MISSING, OwnershipAuditStatus.DUPLICATE}:
            assert row.authoritative_module is None


def test_partial_rows_have_real_semantic_owner_and_explicit_gap() -> None:
    for row in BUSINESS_ONTOLOGY_OWNERSHIP_AUDIT:
        if row.status is not OwnershipAuditStatus.PARTIAL:
            continue
        assert row.authoritative_module, row
        assert importlib.util.find_spec(row.authoritative_module) is not None, row
        assert row.reason and len(row.reason.strip()) >= 12, row
