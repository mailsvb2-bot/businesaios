from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.artifact.projector import CANON_ARTIFACT_PROJECTOR
from application.artifact.registry import CANON_ARTIFACT_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity
from contracts.artifact import Artifact

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/artifact/registry.py")
FACTS = Path("application/artifact/projector.py")
FACT_TYPES = {"artifact.created", "artifact.archived"}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_artifact_inventory_names_one_writer_and_read_projection() -> None:
    row = ontology_ownership_by_entity()["Artifact"]
    assert CANON_ARTIFACT_LIFECYCLE_OWNER is True
    assert CANON_ARTIFACT_PROJECTOR is True
    assert row.authoritative_module == "contracts.artifact"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("application.artifact.registry",)
    assert row.allowed_readers == ("application.artifact.projector",)


def test_artifact_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name)
                and target.id == "CANON_ARTIFACT_LIFECYCLE_OWNER"
                for target in node.targets
            ) and isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_artifact_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in FACT_TYPES:
                    owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_artifact_contract_stores_metadata_not_binary_content() -> None:
    names = {field.name for field in fields(Artifact)}
    assert {"storage_ref", "content_sha256", "media_type"} <= names
    assert names.isdisjoint({"bytes", "content", "blob", "payload", "base64"})


def test_artifact_registry_uses_shared_event_mutation_not_technical_artifact_store() -> None:
    source = (ROOT / REGISTRY).read_text(encoding="utf-8")
    technical_store = (
        ROOT / "runtime/platform/support/storage/base_stores.py"
    ).read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    assert "append_transition_once" in source
    assert "BusinessFactV1(" not in source
    assert "ArtifactStore" not in source
    assert "CANON_ARTIFACT_LIFECYCLE_OWNER" not in technical_store


def test_business_autonomy_bootstrap_wires_artifact_to_existing_event_store() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "ArtifactRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_artifact_registry"' in wiring
    assert "wire_business_ontology_runtime(" in bootstrap
