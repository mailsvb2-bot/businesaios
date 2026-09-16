from __future__ import annotations

from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]


def test_outcome_inventory_names_existing_evidence_owner() -> None:
    row = ontology_ownership_by_entity()["Outcome"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "contracts.business_outcome"
    assert row.storage_owner == "storage.evidence_store"
    assert row.allowed_writers == ("application.evidence.evidence_persistence",)
    assert row.allowed_readers == ("application.outcome.evidence_projection",)
    assert "lineage-only Evidence rows" in row.reason
    assert "legacy history" in row.reason


def test_outcome_full_body_is_written_only_through_canonical_evidence_persistence() -> None:
    persistence = (ROOT / "application/evidence/evidence_persistence.py").read_text(encoding="utf-8")
    projection = (ROOT / "application/outcome/evidence_projection.py").read_text(encoding="utf-8")
    assert "'business_outcome': business_outcome" in persistence
    assert "EvidenceStore" in projection
    assert ".append(" not in projection
    assert "BusinessOutcomeV1.from_feedback(" in projection
    assert "legacy_incomplete_count" in projection
    assert 'not _mapping(row.payload.get("business_outcome"))' in projection
