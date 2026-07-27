from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

import pytest

from scripts.ci.pytest_tools import _aggregate_junit_files, _build_test_shards
from scripts.ci.repository_sources import (
    iter_repository_python_files,
    read_python_source,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_repository_source_scan_is_bounded_and_skips_external_trees(
    tmp_path: Path,
) -> None:
    keep_a = _write(tmp_path / "pkg" / "a.py", "A = 1\n")
    keep_b = _write(tmp_path / "tests" / "test_b.py", "def test_b(): pass\n")
    _write(tmp_path / ".venv" / "ignored.py", "raise AssertionError\n")
    _write(tmp_path / "node_modules" / "ignored.py", "raise AssertionError\n")
    _write(tmp_path / "pkg" / "not_python.txt", "ignored\n")
    symlink = tmp_path / "pkg" / "linked.py"
    try:
        symlink.symlink_to(keep_a)
    except OSError:
        symlink = None

    assert iter_repository_python_files(tmp_path) == (keep_a, keep_b)
    assert read_python_source(keep_a) == "A = 1\n"
    if symlink is not None:
        with pytest.raises(ValueError, match="not a regular source file"):
            read_python_source(symlink)


def test_repository_source_reader_rejects_invalid_bounds_and_large_files(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path / "large.py", "x" * 8)
    with pytest.raises(ValueError, match="max_bytes must be positive"):
        read_python_source(path, max_bytes=0)
    with pytest.raises(ValueError, match="source file exceeds"):
        read_python_source(path, max_bytes=4)
    with pytest.raises(ValueError, match="not a regular source file"):
        read_python_source(tmp_path)


def test_test_shards_are_deterministic_and_bounded(tmp_path: Path) -> None:
    files = tuple(
        _write(tmp_path / f"test_{index}.py", "x" * size)
        for index, size in enumerate((3, 3, 7, 2), start=1)
    )
    shards = _build_test_shards(
        files,
        max_files=2,
        max_source_bytes=8,
    )
    assert shards == ((files[0], files[1]), (files[2],), (files[3],))
    with pytest.raises(ValueError, match="bounds must be positive"):
        _build_test_shards(files, max_files=0, max_source_bytes=1)
    assert _build_test_shards((), max_files=1, max_source_bytes=1) == ()


def test_junit_aggregation_preserves_all_shard_totals(tmp_path: Path) -> None:
    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"
    missing = tmp_path / "missing.xml"
    first.write_text(
        '<testsuite name="a" tests="2" failures="1" errors="0" '
        'skipped="0" time="0.25"/>',
        encoding="utf-8",
    )
    second.write_text(
        '<testsuites><testsuite name="b" tests="3" failures="0" '
        'errors="1" skipped="1" time="0.75"/></testsuites>',
        encoding="utf-8",
    )
    output = tmp_path / "out" / "unit.xml"
    _aggregate_junit_files(
        shard_paths=[first, missing, second],
        output_path=output,
    )
    root = ElementTree.parse(output).getroot()
    assert root.attrib == {
        "tests": "5",
        "failures": "1",
        "errors": "1",
        "skipped": "1",
        "time": "1.000000",
    }
    assert [suite.attrib["name"] for suite in root] == ["a", "b"]


def test_sharded_runner_reports_all_failures_and_keeps_aggregate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from scripts.ci import pytest_tools

    first = _write(tmp_path / "tests" / "test_a.py", "def test_a(): pass\n")
    second = _write(tmp_path / "tests" / "test_b.py", "def test_b(): pass\n")
    junit_root = tmp_path / "junit"
    calls: list[list[str]] = []

    monkeypatch.setattr(pytest_tools, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(pytest_tools, "junit_dir", lambda: junit_root)
    monkeypatch.setattr(
        pytest_tools,
        "_discover_test_files",
        lambda _targets: (first, second),
    )
    monkeypatch.setattr(
        pytest_tools,
        "_write_coverage_honesty_artifact",
        lambda **_kwargs: None,
    )

    def fake_run(**kwargs):
        calls.append(list(kwargs["target_args"]))
        shard_path = junit_root / kwargs["junit_name"]
        shard_path.parent.mkdir(parents=True, exist_ok=True)
        shard_path.write_text(
            '<testsuite name="shard" tests="1" failures="0" '
            'errors="0" skipped="0" time="0.01"/>',
            encoding="utf-8",
        )
        if kwargs["target_args"] == ["tests/test_b.py"]:
            return False, "second shard failed"
        return True, "ok"

    monkeypatch.setattr(pytest_tools, "run_pytest_with_report", fake_run)
    ok, message = pytest_tools.run_pytest_sharded_with_report(
        target_args=["tests"],
        mark_expression="not slow",
        junit_name="unit.xml",
        coverage_name="unit-coverage.xml",
        max_files_per_shard=1,
    )
    assert ok is False
    assert "shard 2/2: second shard failed" in message
    assert calls == [["tests/test_a.py"], ["tests/test_b.py"]]
    aggregate = ElementTree.parse(junit_root / "unit.xml").getroot()
    assert aggregate.attrib["tests"] == "2"


def test_sharded_runner_falls_back_when_targets_have_no_test_files(monkeypatch) -> None:
    from scripts.ci import pytest_tools

    monkeypatch.setattr(pytest_tools, "_discover_test_files", lambda _targets: ())
    monkeypatch.setattr(
        pytest_tools,
        "run_pytest_with_report",
        lambda **kwargs: (True, f"fallback:{kwargs['junit_name']}"),
    )
    assert pytest_tools.run_pytest_sharded_with_report(
        target_args=["tests/missing"],
        mark_expression="not slow",
        junit_name="unit.xml",
        coverage_name="unit-coverage.xml",
    ) == (True, "fallback:unit.xml")


def test_unit_ci_step_delegates_to_bounded_sharded_runner(monkeypatch) -> None:
    from types import SimpleNamespace

    from scripts.ci import step_unit_tests

    monkeypatch.setattr(step_unit_tests, "repo_root", lambda: Path("/repo"))
    monkeypatch.setattr(
        step_unit_tests,
        "project_shape_config",
        lambda _root: SimpleNamespace(
            unit_targets=("tests/unit",),
            unit_mark_expression="not slow",
        ),
    )
    captured: dict[str, object] = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return True, "all shards passed"

    monkeypatch.setattr(
        step_unit_tests,
        "run_pytest_sharded_with_report",
        fake_runner,
    )
    assert step_unit_tests.run() == (True, "unit test gate passed")
    assert captured["target_args"] == ["tests/unit"]
    assert captured["timeout_per_shard"] == 240

    monkeypatch.setattr(
        step_unit_tests,
        "project_shape_config",
        lambda _root: SimpleNamespace(
            unit_targets=(),
            unit_mark_expression="not slow",
        ),
    )
    assert step_unit_tests.run() == (False, "unit target set is empty")


def test_pytest_report_helper_writes_honesty_and_failure_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import json

    from scripts.ci import pytest_tools
    from scripts.ci.subprocess_io import CommandOutcome

    junit_root = tmp_path / "junit"
    coverage_root = tmp_path / "coverage"
    reports_root = tmp_path / "reports"
    monkeypatch.setattr(pytest_tools, "junit_dir", lambda: junit_root)
    monkeypatch.setattr(pytest_tools, "coverage_dir", lambda: coverage_root)
    monkeypatch.setattr(pytest_tools, "reports_dir", lambda: reports_root)

    outcomes = iter(
        (
            CommandOutcome(0, "ok", ""),
            CommandOutcome(1, "failed", "trace"),
            CommandOutcome(124, "", "timeout"),
        )
    )
    captured_args: list[list[str]] = []

    def fake_pytest(args, *, timeout=None):
        captured_args.append(list(args))
        return next(outcomes)

    monkeypatch.setattr(pytest_tools, "run_pytest", fake_pytest)
    common = {
        "target_args": ["tests/unit/test_x.py"],
        "mark_expression": "not slow",
        "junit_name": "nested/unit.xml",
        "coverage_name": "unit-coverage.json",
        "timeout": 9,
    }
    assert pytest_tools.run_pytest_with_report(**common)[0] is True
    failed, failed_message = pytest_tools.run_pytest_with_report(**common)
    assert failed is False
    assert "pytest failed" in failed_message
    timed_out, timeout_message = pytest_tools.run_pytest_with_report(**common)
    assert timed_out is False
    assert "pytest timed out" in timeout_message
    assert all("--junitxml" in args for args in captured_args)

    honesty = json.loads(
        (coverage_root / "unit-coverage.json").read_text(encoding="utf-8")
    )
    assert honesty["claims_code_coverage"] is False
    failure = json.loads(
        (reports_root / "pytest" / "nested-unit.failure.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["returncode"] == 124
    assert pytest_tools._failure_excerpt(CommandOutcome(1, "", "")) == (
        "no pytest output captured"
    )
    assert pytest_tools._diagnostics_stem("") == "pytest"


def test_test_discovery_accepts_files_directories_and_ignores_non_tests(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from scripts.ci import pytest_tools

    direct = _write(tmp_path / "test_direct.py", "def test_direct(): pass\n")
    nested = _write(
        tmp_path / "suite" / "test_nested.py",
        "def test_nested(): pass\n",
    )
    _write(tmp_path / "suite" / "helper.py", "VALUE = 1\n")
    monkeypatch.setattr(pytest_tools, "repo_root", lambda: tmp_path)
    assert pytest_tools._discover_test_files(
        ["test_direct.py", "suite", "missing"]
    ) == tuple(sorted((direct, nested)))


def test_sharded_runner_success_and_unit_step_failure(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    from scripts.ci import pytest_tools, step_unit_tests

    test_file = _write(tmp_path / "tests" / "test_ok.py", "def test_ok(): pass\n")
    junit_root = tmp_path / "junit"
    monkeypatch.setattr(pytest_tools, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(pytest_tools, "junit_dir", lambda: junit_root)
    monkeypatch.setattr(
        pytest_tools,
        "_discover_test_files",
        lambda _targets: (test_file,),
    )
    monkeypatch.setattr(
        pytest_tools,
        "_write_coverage_honesty_artifact",
        lambda **_kwargs: None,
    )

    def successful_shard(**kwargs):
        path = junit_root / kwargs["junit_name"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '<testsuite tests="1" failures="0" errors="0" '
            'skipped="0" time="0"/>',
            encoding="utf-8",
        )
        return True, "ok"

    monkeypatch.setattr(pytest_tools, "run_pytest_with_report", successful_shard)
    assert pytest_tools.run_pytest_sharded_with_report(
        target_args=["tests"],
        mark_expression="not slow",
        junit_name="unit.xml",
        coverage_name="unit-coverage.xml",
    ) == (True, "pytest sharded gate passed: 1 files in 1 shards")

    monkeypatch.setattr(step_unit_tests, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        step_unit_tests,
        "project_shape_config",
        lambda _root: SimpleNamespace(
            unit_targets=("tests/unit",),
            unit_mark_expression="not slow",
        ),
    )
    monkeypatch.setattr(
        step_unit_tests,
        "run_pytest_sharded_with_report",
        lambda **_kwargs: (False, "shard failed"),
    )
    assert step_unit_tests.run() == (False, "shard failed")


def test_repository_scan_handles_os_errors_and_post_stat_growth(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from scripts.ci import repository_sources

    monkeypatch.setattr(
        repository_sources.os,
        "scandir",
        lambda _directory: (_ for _ in ()).throw(PermissionError()),
    )
    assert repository_sources.iter_repository_python_files(tmp_path) == ()

    class BrokenEntry:
        name = "broken.py"
        path = str(tmp_path / "broken.py")

        def is_symlink(self):
            raise OSError("stat failed")

    monkeypatch.setattr(
        repository_sources.os,
        "scandir",
        lambda _directory: (BrokenEntry(),),
    )
    assert repository_sources.iter_repository_python_files(tmp_path) == ()

    class NonFileEntry:
        name = "socket.py"
        path = str(tmp_path / "socket.py")

        def is_symlink(self):
            return False

        def is_dir(self, *, follow_symlinks=False):
            return False

        def is_file(self, *, follow_symlinks=False):
            return False

    monkeypatch.setattr(
        repository_sources.os,
        "scandir",
        lambda _directory: (NonFileEntry(),),
    )
    assert repository_sources.iter_repository_python_files(tmp_path) == ()

    path = _write(tmp_path / "grows.py", "1234")
    real_open = Path.open

    class GrowingReader:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b"12345"

    monkeypatch.setattr(Path, "open", lambda self, *args, **kwargs: GrowingReader())
    with pytest.raises(ValueError, match="source file exceeds"):
        repository_sources.read_python_source(path, max_bytes=4)
    monkeypatch.setattr(Path, "open", real_open)
