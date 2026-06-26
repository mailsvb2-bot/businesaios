from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.ci.paths import repo_root


@dataclass(frozen=True)
class BaselineRequirement:
    requirement_id: str
    title: str
    domain: str
    scenario_ref: str
    required_gates: tuple[str, ...]

    @property
    def scenario_path(self) -> str:
        return self.scenario_ref.split("::", 1)[0]


BASELINE_REQUIREMENTS: tuple[BaselineRequirement, ...] = (
    BaselineRequirement(
        requirement_id="BAIOS-BASE-001",
        title="single DecisionCore flow remains the only canonical decision path",
        domain="decision-core",
        scenario_ref="tests/baseline/test_baseline_contract_scenarios.py::test_baseline_single_decision_flow_contract_is_declared",
        required_gates=("fast", "full", "release", "pre-release"),
    ),
    BaselineRequirement(
        requirement_id="BAIOS-BASE-002",
        title="second-brain surfaces remain forbidden",
        domain="architecture",
        scenario_ref="tests/baseline/test_baseline_contract_scenarios.py::test_baseline_no_second_brain_contract_reuses_arch_lock",
        required_gates=("fast", "full", "release", "pre-release"),
    ),
    BaselineRequirement(
        requirement_id="BAIOS-BASE-003",
        title="runtime execution remains registry-owned and idempotency-locked",
        domain="runtime",
        scenario_ref="tests/baseline/test_baseline_contract_scenarios.py::test_baseline_runtime_execution_contract_has_registry_lock",
        required_gates=("fast", "full", "release", "pre-release"),
    ),
    BaselineRequirement(
        requirement_id="BAIOS-BASE-004",
        title="CI, build, and release gates must include the baseline matrix contour",
        domain="ci",
        scenario_ref="tests/baseline/test_baseline_contract_scenarios.py::test_baseline_ci_build_release_gate_sees_matrix",
        required_gates=("fast", "full", "release", "pre-release"),
    ),
    BaselineRequirement(
        requirement_id="BAIOS-BASE-005",
        title="public surfaces remain explicit and import-testable",
        domain="public-surface",
        scenario_ref="tests/baseline/test_baseline_contract_scenarios.py::test_baseline_public_surface_contract_has_import_scenario",
        required_gates=("fast", "full", "release", "pre-release"),
    ),
    BaselineRequirement(
        requirement_id="BAIOS-BASE-006",
        title="generated and runtime artifacts stay outside source changes",
        domain="repo-hygiene",
        scenario_ref="tests/baseline/test_baseline_contract_scenarios.py::test_baseline_generated_artifact_contract_is_blocked",
        required_gates=("fast", "full", "release", "pre-release"),
    ),
    BaselineRequirement(
        requirement_id="BAIOS-BASE-007",
        title="storage compatibility remains covered by explicit regression mapping",
        domain="storage",
        scenario_ref="tests/baseline/test_baseline_contract_scenarios.py::test_baseline_storage_compatibility_contract_is_mapped",
        required_gates=("fast", "full", "release", "pre-release"),
    ),
    BaselineRequirement(
        requirement_id="BAIOS-BASE-008",
        title="billing recovery remains covered by explicit regression mapping",
        domain="billing",
        scenario_ref="tests/baseline/test_baseline_contract_scenarios.py::test_baseline_billing_recovery_contract_is_mapped",
        required_gates=("fast", "full", "release", "pre-release"),
    ),
)


def baseline_requirement_ids() -> tuple[str, ...]:
    return tuple(requirement.requirement_id for requirement in BASELINE_REQUIREMENTS)


def missing_scenario_paths(root: Path | None = None) -> tuple[str, ...]:
    base = repo_root() if root is None else root
    missing = {
        requirement.scenario_path
        for requirement in BASELINE_REQUIREMENTS
        if not (base / requirement.scenario_path).exists()
    }
    return tuple(sorted(missing))


def requirements_for_gate(gate: str) -> tuple[BaselineRequirement, ...]:
    return tuple(requirement for requirement in BASELINE_REQUIREMENTS if gate in requirement.required_gates)


def required_gates() -> tuple[str, ...]:
    gates: set[str] = set()
    for requirement in BASELINE_REQUIREMENTS:
        gates.update(requirement.required_gates)
    return tuple(sorted(gates))


__all__ = [
    "BASELINE_REQUIREMENTS",
    "BaselineRequirement",
    "baseline_requirement_ids",
    "missing_scenario_paths",
    "required_gates",
    "requirements_for_gate",
]
