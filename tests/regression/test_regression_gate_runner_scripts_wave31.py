from pathlib import Path


def test_runner_scripts_are_present_wave31() -> None:
    assert Path("scripts/run_regression_gate.py").exists()
    assert Path("scripts/run_formal_proof_obligations.py").exists()
    assert Path("scripts/run_regression_gate_strength.py").exists()
    assert Path("scripts/run_project_snapshot_bundle.py").exists()
