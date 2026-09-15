from __future__ import annotations

import ast
from pathlib import Path

from application.ontology import CANON_ONTOLOGY_EVENT_FACT_MUTATION

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
OWNER = Path("application/ontology/event_fact_lifecycle.py")
ENTITY_REGISTRIES = (
    Path("application/organization/registry.py"),
    Path("application/person/registry.py"),
)


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_ontology_event_fact_mutation_owner_marker_is_unique() -> None:
    assert CANON_ONTOLOGY_EVENT_FACT_MUTATION is True
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_ONTOLOGY_EVENT_FACT_MUTATION"
                for target in node.targets
            ):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [OWNER]


def test_event_sourced_entity_registries_delegate_durable_mutation() -> None:
    for path in ENTITY_REGISTRIES:
        source = (ROOT / path).read_text(encoding="utf-8")
        assert "EventFactLifecycleWriter" in source
        assert "BusinessFactV1(" not in source
        assert "build_idempotency_key(" not in source
        assert "IdempotencyState" not in source
