from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import ontology_ownership_by_entity
from contracts.growth_hypothesis import CANON_GROWTH_HYPOTHESIS_CONTRACT, GrowthHypothesis, GrowthHypothesisV1
from core.growth.strategy.contracts import GrowthHypothesisV1 as CoreGrowthHypothesisV1

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("contracts", "core", "application", "runtime", "execution", "crm", "billing")
OWNER = Path("contracts/growth_hypothesis.py")
BACKLOG = Path("core/growth/strategy/backlog_store.py")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_hypothesis_semantic_contract_has_one_class_definition() -> None:
    assert CANON_GROWTH_HYPOTHESIS_CONTRACT is True
    assert GrowthHypothesis is GrowthHypothesisV1
    assert CoreGrowthHypothesisV1 is GrowthHypothesisV1
    definitions = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "GrowthHypothesisV1":
                definitions.append(path.relative_to(ROOT))
    assert definitions == [OWNER]


def test_hypothesis_inventory_names_existing_backlog_owner() -> None:
    row = ontology_ownership_by_entity()["Hypothesis"]
    assert row.authoritative_module == "contracts.growth_hypothesis"
    assert row.storage_owner == "core.growth.strategy.backlog_store"
    assert row.allowed_writers == ("core.growth.strategy.backlog_store",)
    assert row.allowed_readers == ("core.growth.strategy.backlog_store",)


def test_growth_core_contract_is_compatibility_reexport_not_second_owner() -> None:
    source = (ROOT / "core/growth/strategy/contracts.py").read_text(encoding="utf-8")
    assert "from contracts.growth_hypothesis import (" in source
    assert "class GrowthHypothesisV1" not in source


def test_hypothesis_event_chronology_stays_in_backlog_store() -> None:
    writers = set()
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        if "GROWTH_HYPOTHESIS_CREATED" in source and ("log.emit(" in source or "_emit_once(" in source):
            writers.add(path.relative_to(ROOT))
    assert writers == {BACKLOG}


def test_growth_event_types_reexport_canonical_vocabulary() -> None:
    source = (ROOT / "core/growth/strategy/event_types.py").read_text(encoding="utf-8")
    assert "from core.events.event_types import (" in source
    assert "growth_hypothesis_created@v1" not in source
    assert "growth_hypothesis_state@v1" not in source
