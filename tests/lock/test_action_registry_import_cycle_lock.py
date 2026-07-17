from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run_fresh_import(code: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        completed.stdout + completed.stderr
    )


@pytest.mark.lock
def test_runtime_registry_imports_before_core_actions_without_cycle() -> None:
    _run_fresh_import(
        "import runtime.boot.actions_registry as registry\n"
        "import core.actions as actions\n"
        "assert actions.ALLOWED_ACTIONS == tuple(sorted(registry.SPECS))\n"
    )


@pytest.mark.lock
def test_core_action_name_imports_before_runtime_registry_without_cycle() -> None:
    _run_fresh_import(
        "from core.actions import ACTION_ROUTE_LEAD_V1\n"
        "import runtime.boot.actions_registry as registry\n"
        "assert ACTION_ROUTE_LEAD_V1 in registry.SPECS\n"
    )
