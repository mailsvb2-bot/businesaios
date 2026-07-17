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
    BaselineRequirement("BAIOS-BASE-001", "single DecisionCore flow remains canonical", "decision-core", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_single_decision_flow_contract_is_declared", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-002", "second-brain surfaces remain forbidden", "architecture", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_no_second_brain_contract_reuses_arch_lock", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-003", "runtime execution remains registry-owned", "runtime", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_runtime_execution_contract_has_registry_lock", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-004", "CI build and release gates see the matrix", "ci", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_ci_build_release_gate_sees_matrix", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-005", "public surfaces remain import-testable", "public-surface", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_public_surface_contract_has_import_scenario", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-006", "generated artifacts stay out of source changes", "repo-hygiene", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_generated_artifact_contract_is_blocked", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-007", "storage compatibility remains regression-mapped", "storage", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_storage_compatibility_contract_is_mapped", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-008", "billing recovery remains regression-mapped", "billing", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_billing_recovery_contract_is_mapped", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-009", "user scenario acceptance gate remains declared", "acceptance", "tests/baseline/test_baseline_contract_scenarios.py::test_baseline_user_scenario_acceptance_gate_is_declared", ("acceptance",)),
    BaselineRequirement("BAIOS-BASE-010", "DecisionCore identity cannot be replaced after registration", "decision-core", "tests/lock/test_decision_singleton_execution_path_lock.py::test_locked_path_accepts_only_the_registered_issuer_identity", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-011", "signed demand routing preserves the public RoutingDecision contract", "demand-routing", "tests/business_critical/test_canonical_demand_route_decision.py::test_bridge_preserves_public_routing_decision_from_signed_envelope", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-012", "recommendations cannot issue or execute actions", "decision-boundary", "tests/lock/test_recommendation_execution_boundary.py::test_recommendation_service_has_no_decision_issuance_aliases", ("fast", "full", "release", "pre-release")),
    BaselineRequirement("BAIOS-BASE-013", "application execution accepts only signed envelopes", "execution-boundary", "tests/lock/test_recommendation_execution_boundary.py::test_application_execution_accepts_only_signed_envelopes", ("fast", "full", "release", "pre-release")),
)


def baseline_requirement_ids() -> tuple[str, ...]:
    return tuple(requirement.requirement_id for requirement in BASELINE_REQUIREMENTS)


def baseline_scenario_refs() -> tuple[str, ...]:
    return tuple(requirement.scenario_ref for requirement in BASELINE_REQUIREMENTS)


def missing_scenario_paths(root: Path | None = None) -> tuple[str, ...]:
    base = repo_root() if root is None else root
    missing = {requirement.scenario_path for requirement in BASELINE_REQUIREMENTS if not (base / requirement.scenario_path).exists()}
    return tuple(sorted(missing))


def required_gates() -> tuple[str, ...]:
    gates: set[str] = set()
    for requirement in BASELINE_REQUIREMENTS:
        gates.update(requirement.required_gates)
    return tuple(sorted(gates))


__all__ = [
    "BASELINE_REQUIREMENTS",
    "BaselineRequirement",
    "baseline_requirement_ids",
    "baseline_scenario_refs",
    "missing_scenario_paths",
    "required_gates",
]
