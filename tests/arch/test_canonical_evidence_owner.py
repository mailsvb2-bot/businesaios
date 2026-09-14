from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from storage.evidence_store import CANON_STORAGE_EVIDENCE_STORE, EVIDENCE_LINEAGE_STAGES, EvidenceRecord


def test_evidence_has_one_selected_canonical_owner() -> None:
    row = ontology_ownership_by_entity()["Evidence"]
    assert row.status is OwnershipAuditStatus.PARTIAL
    assert row.authoritative_module == "storage.evidence_store"
    assert row.storage_owner == "storage.evidence_store"
    assert CANON_STORAGE_EVIDENCE_STORE is True


def test_canonical_evidence_contract_contains_phase3_fields_and_lineage() -> None:
    names = {item.name for item in fields(EvidenceRecord)}
    required = {
        "evidence_id", "source", "source_type", "business_id", "observed_at",
        "confidence", "privacy_class", "retention_policy", "lineage",
    }
    assert required <= names
    assert EVIDENCE_LINEAGE_STAGES == ("source", "normalization", "derived_fact", "decision", "action", "outcome")


def test_no_second_canonical_evidence_store_marker_exists() -> None:
    owners: list[str] = []
    blocked = {".git", ".venv", "venv", "__pycache__", "node_modules"}
    for path in Path(".").rglob("*.py"):
        if any(part in blocked for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and "EVIDENCE" in target.id and "STORE" in target.id:
                    if isinstance(node.value, ast.Constant) and node.value.value is True:
                        owners.append(f"{path.as_posix()}:{target.id}")
    assert owners == ["storage/evidence_store.py:CANON_STORAGE_EVIDENCE_STORE"]
