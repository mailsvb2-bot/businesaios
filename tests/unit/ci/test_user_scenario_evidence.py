from __future__ import annotations

import json
from contextlib import nullcontext

from scripts.ci import step_user_scenario_gate as gate
from scripts.ci.subprocess_io import CommandOutcome
from scripts.ci.user_scenario_targets import USER_SCENARIO_EVIDENCE_NAME, USER_SCENARIOS


def _materialize_targets(root) -> None:
    for _, target in USER_SCENARIOS:
        path = root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# scenario\n", encoding="utf-8")


def test_rust_evidence_preserves_actual_runner_cases(monkeypatch, tmp_path) -> None:
    crate = tmp_path / "rust" / "businessaios_safety_core"
    fixture = tmp_path / "safety_fixtures" / "businessaios_user_scenario_matrix_golden.json"
    crate.mkdir(parents=True)
    fixture.parent.mkdir(parents=True)
    fixture.write_text("{}", encoding="utf-8")
    actual = {
        "version": "businessaios_user_scenario_matrix.v1",
        "passed": True,
        "total_cases": 1,
        "cases": [{"name": "actual-case", "scenario": "cli_run", "passed": True}],
    }
    monkeypatch.setattr(gate, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(gate.shutil, "which", lambda command: "cargo")
    monkeypatch.setattr(gate, "isolated_cargo_target", lambda scope: nullcontext({}))
    monkeypatch.setattr(gate, "run_command", lambda *args, **kwargs: CommandOutcome(0, json.dumps(actual), ""))

    evidence = gate._rust_evidence()

    assert evidence["status"] == "PASS"
    assert evidence["version"] == actual["version"]
    assert evidence["cases"] == actual["cases"]


def test_gate_runs_all_scenarios_and_records_failure_diagnostics(monkeypatch, tmp_path) -> None:
    _materialize_targets(tmp_path)
    report_dir = tmp_path / "artifacts" / "ci"
    report_dir.mkdir(parents=True)
    monkeypatch.setenv("BAIOS_CI_TARGET_SHA", "f" * 40)
    monkeypatch.setattr(gate, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(gate, "reports_dir", lambda: report_dir)
    monkeypatch.setattr(
        gate,
        "_rust_evidence",
        lambda: {"status": "PASS", "message": "rust passed", "version": "v1", "cases": []},
    )
    called: list[str] = []

    def fake_pytest(*, target_args, **kwargs):
        target = target_args[0]
        called.append(target)
        return (False, "simulated failure") if target.endswith("test_cli_run_smoke.py") else (True, "passed")

    monkeypatch.setattr(gate, "run_pytest_with_report", fake_pytest)

    ok, message = gate.run()
    payload = json.loads((report_dir / USER_SCENARIO_EVIDENCE_NAME).read_text(encoding="utf-8"))

    assert ok is False
    assert "cli_run:FAIL" in message
    assert called == [target for _, target in USER_SCENARIOS]
    assert payload["exact_sha"] == "f" * 40
    assert payload["status"] == "FAIL"
    assert [item["id"] for item in payload["scenarios"]] == [scenario_id for scenario_id, _ in USER_SCENARIOS]
    assert [item["status"] for item in payload["scenarios"]] == ["PASS", "PASS", "FAIL", "PASS", "PASS"]
    assert payload["scenarios"][2]["junit"] == "junit/user-scenario-3.xml"
    assert payload["scenarios"][2]["diagnostics"] == "pytest/user-scenario-3.failure.json"
