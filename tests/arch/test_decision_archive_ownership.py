from __future__ import annotations

import ast
from pathlib import Path

from core.ai.decision_archive import CANON_DECISION_ARCHIVE_STORAGE_OWNER

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "core", "execution")
RUNTIME_WRITER = Path("application/decision_runtime/emission.py")
VERIFICATION_DIRECT_WRITER = Path("runtime/canonical_e2e_smoke.py")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_decision_archive_storage_owner_marker_is_canonical() -> None:
    assert CANON_DECISION_ARCHIVE_STORAGE_OWNER is True


def test_decision_archive_direct_puts_do_not_create_second_runtime_writer() -> None:
    direct_puts = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "put":
                continue
            owner = node.func.value
            name = owner.id if isinstance(owner, ast.Name) else owner.attr if isinstance(owner, ast.Attribute) else ""
            if name not in {"archive", "_archive", "decision_archive"}:
                continue
            direct_puts.append((path.relative_to(ROOT), node.lineno))
    assert {path for path, _ in direct_puts} == {RUNTIME_WRITER, VERIFICATION_DIRECT_WRITER}


def test_runtime_decision_archive_writer_matches_ontology_inventory() -> None:
    from canon.business_ontology_inventory import ontology_ownership_by_entity

    row = ontology_ownership_by_entity()["Decision"]
    assert row.allowed_writers == ("application.decision_runtime.emission",)
    assert set(row.allowed_readers) == {"runtime.replay", "runtime.recovery"}
