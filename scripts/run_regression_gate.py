from __future__ import annotations

import sys
from pathlib import Path

from scripts.ci.subprocess_io import run_command

ROOT = Path(__file__).resolve().parents[1]
TESTS = [
    "tests/regression/test_regression_gate_decision_core_aliases_wave31.py",
    "tests/regression/test_regression_gate_runtime_paths_wave31.py",
    "tests/regression/test_regression_gate_architecture_wave31.py",
    "tests/regression/test_regression_gate_contract_diff_wave31.py",
    "tests/regression/test_regression_gate_trace_equivalence_wave31.py",
    "tests/regression/test_regression_gate_fail_closed_matrix_wave31.py",
    "tests/regression/test_regression_gate_observability_boot_completeness_wave31.py",
    "tests/regression/test_regression_gate_runtime_application_ports_wave31.py",
    "tests/regression/test_regression_gate_formal_invariants_wave31.py",
    "tests/regression/test_regression_gate_formal_model_wave31.py",
    "tests/regression/test_regression_gate_tla_assets_wave31.py",
    "tests/regression/test_regression_gate_replay_harness_wave31.py",
    "tests/regression/test_regression_gate_trace_corpus_wave31.py",
    "tests/regression/test_regression_gate_mutation_strength_wave31.py",
    "tests/regression/test_regression_gate_runner_scripts_wave31.py",
    "tests/regression/test_regression_gate_project_snapshot_bundle_wave31.py",
]


def main() -> int:
    command = [sys.executable, "-m", "pytest", *TESTS, "-q"]
    return run_command(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
