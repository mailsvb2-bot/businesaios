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

    assert command[:3] == [sys.executable, "-m", "coverage"]


def test_coverage_gate_does_not_hardcode_bare_python_command() -> None:
    text = Path("scripts/ci/step_code_coverage.py").read_text(encoding="utf-8")

    assert '["python", "-m", "coverage"' not in text
    assert '["python", "-c", "import coverage' not in text
