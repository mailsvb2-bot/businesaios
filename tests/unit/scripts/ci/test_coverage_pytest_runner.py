from __future__ import annotations

import os
import sys
from types import ModuleType

from scripts.ci.coverage_pytest_runner import run
from scripts.ci.step_code_coverage import (
    COVERAGE_SHARDS,
    HEADLESS_COVERAGE_TIMEOUT_SECONDS,
    CoverageShard,
    _coverage_run_command,
)


def test_coverage_runner_saves_parallel_data_before_return(monkeypatch) -> None:
    events: list[object] = []

    class _FakeCoverage:
        def __init__(
            self,
            *,
            branch: bool,
            source: list[str],
            omit: list[str],
            data_suffix: bool,
        ) -> None:
            events.append(("init", branch, source, omit, data_suffix))

        def start(self) -> None:
            events.append("start")

        def stop(self) -> None:
            events.append("stop")

        def save(self) -> None:
            events.append("save")

    coverage_module = ModuleType("coverage")
    coverage_module.Coverage = _FakeCoverage
    pytest_module = ModuleType("pytest")

    def _pytest_main(argv: list[str]) -> int:
        events.append(
            (
                "pytest",
                argv,
                os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"),
                os.environ.get("PYTHONNOUSERSITE"),
            )
        )
        return 0

    pytest_module.main = _pytest_main
    monkeypatch.setitem(sys.modules, "coverage", coverage_module)
    monkeypatch.setitem(sys.modules, "pytest", pytest_module)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "0")
    monkeypatch.delenv("PYTHONNOUSERSITE", raising=False)

    assert run(["-q", "tests/example.py"]) == 0
    assert events == [
        (
            "init",
            True,
            ["."],
            [
                "*/.venv*/*",
                "*/venv/*",
                "*/site-packages/*",
                "*/dist-packages/*",
            ],
            True,
        ),
        "start",
        ("pytest", ["-q", "tests/example.py"], "1", "1"),
        "stop",
        "save",
    ]


def test_coverage_shard_uses_deterministic_runner_module() -> None:
    shard = CoverageShard(
        name="headless",
        timeout=HEADLESS_COVERAGE_TIMEOUT_SECONDS,
        targets=("tests/integration/headless/test_cli_run_smoke.py",),
    )

    command = _coverage_run_command(shard)

    assert command[:3] == [sys.executable, "-m", "scripts.ci.coverage_pytest_runner"]
    assert "tests/integration/headless/test_cli_run_smoke.py" in command
    assert command[-2:] == ["-m", "not slow and not gate"]


def test_headless_coverage_shards_use_coverage_aware_budget() -> None:
    headless_shards = tuple(
        shard for shard in COVERAGE_SHARDS if shard.name.startswith("integration-headless-")
    )

    assert len(headless_shards) == 3
    assert HEADLESS_COVERAGE_TIMEOUT_SECONDS == 600
    assert {shard.timeout for shard in headless_shards} == {
        HEADLESS_COVERAGE_TIMEOUT_SECONDS
    }
