from __future__ import annotations

from scripts.ci.paths import coverage_dir, execution_dir


def test_gate_execution_metadata_is_written_outside_coverage_directory(monkeypatch) -> None:
    from scripts.ci import execution as execution_module

    legacy_path = coverage_dir() / "doctor.xml"
    if legacy_path.exists():
        legacy_path.unlink()

    monkeypatch.setattr(execution_module, "plan_for_gate", lambda gate: type("Plan", (), {"gate": gate, "steps": ()})())

    report = execution_module.execute(
        execution_module.ExecutionRequest(gate="doctor", emit_report=True, emit_junit=False, emit_coverage=True)
    )

    assert report.success
    assert (execution_dir() / "doctor.xml").exists()
    assert not legacy_path.exists()
