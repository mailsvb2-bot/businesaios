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
    "task.created",
    "task.ready",
    "task.started",
    "task.waiting",
    "task.paused",
    "task.blocked",
    "task.succeeded",
    "task.completed",
    "task.failed",
    "task.cancelled",
    "task.compensating",
    "task.artifact_attached",
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
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "artifact_registry = ArtifactRegistry(" in wiring
    assert "artifact_registry=artifact_registry" in wiring
    assert '"_artifact_registry": artifact_registry' in wiring
    assert '"_task_registry"' in wiring
    assert "wire_business_ontology_runtime(" in bootstrap



def test_phase9_task_runtime_reuses_canonical_queue_and_lock_owners() -> None:
    queue_adapter = (ROOT / "runtime/queue/job_dispatcher.py").read_text(encoding="utf-8")
    conflict_control = (ROOT / "application/task/registry.py").read_text(encoding="utf-8")

    assert "from runtime.queue.job_contract import" in queue_adapter
    assert "CANON_DURABLE_TASK_QUEUE_ADAPTER = True" in queue_adapter
    assert "JobDispatchRequest" in queue_adapter
    assert "self._dispatcher.dispatch(request)" in queue_adapter
    assert "class JobScheduler" not in queue_adapter
    assert "class JobStore" not in queue_adapter

    assert "from reliability.distributed_lock import DistributedLock" in conflict_control
    assert "CANON_DURABLE_TASK_CONFLICT_CONTROL = True" in conflict_control
    assert "self._lock.acquire(" in conflict_control
    assert "self._lock.release(" in conflict_control
    assert "class InMemoryDistributedLock" not in conflict_control
