from __future__ import annotations

from scripts.ci.baseline_contract import BASELINE_REQUIREMENTS, missing_scenario_paths, required_gates
from scripts.ci.plan_registry import plan_for_gate

_STEP_NAME = "baseline-contract"


def _gate_has_baseline_contract(gate: str) -> bool:
    return _STEP_NAME in tuple(step.name for step in plan_for_gate(gate).steps)


def run() -> tuple[bool, str]:
    if not BASELINE_REQUIREMENTS:
        return False, "baseline contract matrix is empty"

    duplicate_ids = sorted(
        requirement_id
        for requirement_id in {item.requirement_id for item in BASELINE_REQUIREMENTS}
        if sum(1 for item in BASELINE_REQUIREMENTS if item.requirement_id == requirement_id) > 1
    )
    if duplicate_ids:
        return False, "duplicate baseline requirement ids: " + ", ".join(duplicate_ids)

    missing_paths = missing_scenario_paths()
    if missing_paths:
        return False, "baseline scenario path(s) missing: " + ", ".join(missing_paths[:20])

    missing_gates = tuple(gate for gate in required_gates() if not _gate_has_baseline_contract(gate))
    if missing_gates:
        return False, "baseline contract not wired into gate(s): " + ", ".join(missing_gates)

    return True, f"baseline contract matrix passed: {len(BASELINE_REQUIREMENTS)} requirement(s)"


__all__ = ["run"]
