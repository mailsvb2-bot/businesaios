from __future__ import annotations

import ast
from pathlib import Path

from application.task.projector import CANON_DURABLE_TASK_PROJECTOR
from application.task.registry import CANON_DURABLE_TASK_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/task/registry.py")
FACTS = Path("application/task/facts.py")
FACT_TYPES = {
    "task.created", "task.started", "task.completed", "task.failed", "task.cancelled"
}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_task_inventory_names_one_writer_and_read_projection() -> None:
    row = ontology_ownership_by_entity()["Task"]
    assert CANON_DURABLE_TASK_LIFECYCLE_OWNER is True
    assert CANON_DURABLE_TASK_PROJECTOR is True
    assert row.authoritative_module == "contracts.task"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("application.task.registry",)
    assert row.allowed_readers == ("application.task.projector",)


def test_durable_task_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name)
                and target.id == "CANON_DURABLE_TASK_LIFECYCLE_OWNER"
                for target in node.targets
            ) and isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_task_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in FACT_TYPES:
                    owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_task_registry_delegates_durable_mutation_to_shared_owner() -> None:
    source = (ROOT / REGISTRY).read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    assert "BusinessFactV1(" not in source
    assert "build_idempotency_key(" not in source
    assert "IdempotencyState" not in source


def test_business_autonomy_bootstrap_wires_task_to_existing_event_store() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    assert (
        "DurableTaskRegistry(event_store=customer_event_store, "
        "idempotency_store=distributed['idempotency'])"
    ) in bootstrap
    assert "service._task_registry = task_registry" in bootstrap
