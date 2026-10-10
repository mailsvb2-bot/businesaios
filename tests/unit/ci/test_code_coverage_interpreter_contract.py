from __future__ import annotations

import sys
from pathlib import Path

from scripts.ci.step_code_coverage import CoverageShard, _coverage_run_command, _python_command


def test_coverage_gate_uses_current_interpreter_for_python_commands() -> None:
    assert _python_command("-m", "coverage") == [sys.executable, "-m", "coverage"]

    command = _coverage_run_command(
        CoverageShard(
            name="contract",
            timeout=1,
            targets=("tests/unit",),
        )
    )

    assert command[:3] == [
        sys.executable,
        "-m",
        "scripts.ci.coverage_pytest_runner",
    ]


def test_coverage_gate_does_not_hardcode_bare_python_command() -> None:
    text = Path("scripts/ci/step_code_coverage.py").read_text(encoding="utf-8")

    assert '["python", "-m", "coverage"' not in text
    assert '["python", "-c", "import coverage' not in text


def test_coverage_gate_blocks_malformed_json_and_writes_evidence(monkeypatch, tmp_path) -> None:
    import json
    from types import SimpleNamespace
    from scripts.ci import step_code_coverage as coverage

    paths = {
        "json": tmp_path / "coverage.json",
        "xml": tmp_path / "coverage.xml",
        "html": tmp_path / "html",
        "summary": tmp_path / "coverage_summary.json",
    }
    monkeypatch.setattr(coverage, "_coverage_paths", lambda: paths)
    monkeypatch.setattr(coverage, "_coverage_available", lambda: True)
    monkeypatch.setattr(coverage, "COVERAGE_SHARDS", ())
    monkeypatch.setattr(
        coverage, "run_command",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )

    for contents, violation in (
        (None, "coverage_json_missing"),
        ("", "coverage_json_invalid"),
        ("not-json", "coverage_json_invalid"),
        ("[]", "coverage_json_invalid_structure"),
        ('{"totals": null}', "coverage_json_invalid_structure"),
    ):
        if contents is None:
            paths["json"].unlink(missing_ok=True)
        else:
            paths["json"].write_text(contents, encoding="utf-8")
        ok, message = coverage.run()
        summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
        assert ok is False
        assert violation in message
        assert summary["status"] == "blocked"
        assert summary["violations"] == [violation]
        assert summary["claims_production_ready"] is False
        assert summary["json_command_returncode"] == 0
