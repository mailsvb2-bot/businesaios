from __future__ import annotations

from pathlib import Path

from canon.academic_target_architecture import (
    CANONICAL_EXECUTION_PATH,
    CANONICAL_LAYER_STACK,
    CURRENT_RUNTIME_ENFORCEMENT_SLICE,
    FORBIDDEN_DEPENDENCY_EDGES,
    TRANSITION_NAMESPACE_TARGETS,
)

ROOT = Path(__file__).resolve().parents[2]


def test_academic_target_stack_is_present() -> None:
    assert CANONICAL_LAYER_STACK[:6] == (
        "kernel",
        "domain",
        "application",
        "ports",
        "adapters",
        "entrypoints",
    )


def test_runtime_enforcement_slice_is_subpath_of_canonical_execution_path() -> None:
    assert CURRENT_RUNTIME_ENFORCEMENT_SLICE == (
        "DecisionCore",
        "GovernanceChain",
        "ActionExecutor",
    )
    assert CANONICAL_EXECUTION_PATH[3] == "DecisionCore"
    assert "Verification" in CANONICAL_EXECUTION_PATH
    assert "Evidence" in CANONICAL_EXECUTION_PATH


def test_forbidden_edges_cover_core_runtime_inversion() -> None:
    assert ("domain", "runtime") in FORBIDDEN_DEPENDENCY_EDGES
    assert ("kernel", "runtime") in FORBIDDEN_DEPENDENCY_EDGES


def test_transition_namespace_targets_cover_debt_zones() -> None:
    assert TRANSITION_NAMESPACE_TARGETS["boot"] == ("bootstrap",)
    assert "entrypoints.api" in TRANSITION_NAMESPACE_TARGETS["interfaces.api"]


def test_academic_canon_docs_exist() -> None:
    assert (ROOT / "docs" / "CANON_ACADEMIC_TARGET_ARCHITECTURE_V1.md").exists()
    assert (ROOT / "docs" / "CANON_NAMESPACE_MIGRATION_MAP_V1.md").exists()
