from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from storage.evidence_store import (
    CANON_STORAGE_EVIDENCE_STORE,
    EVIDENCE_LINEAGE_STAGES,
    EvidenceRecord,
    EvidenceStore,
    InMemoryEvidenceStore,
)


def test_evidence_has_one_selected_canonical_owner() -> None:
    row = ontology_ownership_by_entity()["Evidence"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "storage.evidence_store"
    assert row.storage_owner == "storage.evidence_store"
    assert CANON_STORAGE_EVIDENCE_STORE is True
    assert isinstance(InMemoryEvidenceStore(), EvidenceStore)


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


def test_phase0_audit_does_not_report_evidence_as_duplicate_after_owner_selection() -> None:
    text = Path("docs/canon/BUSINESSAIOS_NEXT_PHASE0_AUDIT.md").read_text(encoding="utf-8")
    duplicate_line = next(line for line in text.splitlines() if line.startswith("- **DUPLICATE/ambiguous ownership:**"))
    assert "Evidence" not in duplicate_line.split(":**", 1)[-1].split(".", 1)[0]
    assert "Evidence ownership is DONE" in duplicate_line


def test_business_autonomy_bootstrap_does_not_restore_distributed_evidence_as_active_store() -> None:
    text = Path("runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    assert "DistributedEvidenceStore(" not in text
    assert "migrate_legacy_distributed_evidence" in text
    assert "'evidence': canonical_evidence" in text


def test_process_discovery_owner_observations_are_wired_to_canonical_evidence_store() -> None:
    adapter_text = Path("application/process_discovery/canonical_adapters.py").read_text(encoding="utf-8")
    router_text = Path("adapters/api/fastapi/router_adapter.py").read_text(encoding="utf-8")
    assert "evidence_store: EvidenceStore" in adapter_text
    assert "dependency_container.canonical_evidence_store()" in router_text


def test_all_active_evidence_record_writers_are_declared_in_the_ownership_inventory() -> None:
    row = ontology_ownership_by_entity()["Evidence"]
    roots = (Path("application"), Path("runtime"), Path("execution"), Path("core"), Path("adapters"), Path("entrypoints"))
    writers: set[str] = set()
    blocked = {"__pycache__", ".venv", "venv"}
    for root in roots:
        for path in root.rglob("*.py"):
            if any(part in blocked for part in path.parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
                if name == "EvidenceRecord":
                    writers.add(path.with_suffix("").as_posix().replace("/", "."))
    assert writers == set(row.allowed_writers)


def test_business_autonomy_evidence_semantics_have_one_projection_owner() -> None:
    projection = Path("application/business_autonomy/evidence_projection.py").read_text(encoding="utf-8")
    persistence = Path("application/business_autonomy/persistence.py").read_text(encoding="utf-8")
    runtime_view = Path("runtime/business_autonomy/distributed_runtime_views.py").read_text(encoding="utf-8")
    assert "EvidenceRecord(" in projection
    assert "EvidenceRecord(" not in persistence
    assert "EvidenceRecord(" not in runtime_view
    assert "append_business_autonomy_evidence" in persistence
    assert "append_business_autonomy_evidence" in runtime_view


def test_business_autonomy_file_evidence_surface_remains_canonical_fed_mirror() -> None:
    text = Path("runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    assert "Local file surface for dev/test/admin proof, fed from the canonical path." in text
    primary_index = text.index("record = self.primary.append_result(result)")
    mirror_index = text.index("self.mirror.append_result(result)", primary_index)
    assert primary_index < mirror_index


def test_legacy_distributed_evidence_store_is_never_constructed_by_active_runtime() -> None:
    roots = (Path("application"), Path("runtime"), Path("execution"), Path("core"), Path("adapters"), Path("entrypoints"))
    constructors: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
                if name == "DistributedEvidenceStore":
                    constructors.append(path.as_posix())
    assert constructors == []
