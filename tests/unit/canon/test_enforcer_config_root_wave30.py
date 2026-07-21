from __future__ import annotations

from pathlib import Path

import pytest

import canon.enforcer.checks_files as checks_files
from canon.enforcer.reporting import EnforcerReport
from canon.repository_sources import RepositorySourceError


def _write(root: Path, relative: str, text: str = "VALUE = 1\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _kinds(report: EnforcerReport) -> list[str]:
    return [item.kind for item in report.violations]


def test_duplicate_config_scan_includes_top_level_config_with_precomputed_inventory(tmp_path: Path) -> None:
    top_level = _write(tmp_path, "config/env_flags.py")
    runtime = _write(tmp_path, "runtime/platform/config/env_flags.py")
    unrelated = _write(tmp_path, "core/other.py")

    report = EnforcerReport(ok=True)
    checks_files.check_duplicate_config_roots(
        report,
        tmp_path,
        source_files=(runtime, unrelated),
    )

    assert _kinds(report) == ["config-duplication-risk"]
    violation = report.violations[0]
    assert violation.path == "runtime/platform/config/env_flags.py"
    assert violation.hint == "Also exists at config/env_flags.py. Ensure ownership is explicit."
    assert top_level.exists()


def test_duplicate_config_scan_deduplicates_precomputed_top_level_paths(tmp_path: Path) -> None:
    top_level = _write(tmp_path, "config/settings.py")
    runtime = _write(tmp_path, "runtime/config/settings.py")

    report = EnforcerReport(ok=True)
    checks_files.check_duplicate_config_roots(
        report,
        tmp_path,
        source_files=(top_level, runtime),
    )

    assert _kinds(report) == ["config-duplication-risk"]


def test_duplicate_config_scan_reports_top_level_inventory_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _write(tmp_path, "runtime/config/settings.py")

    def fail_inventory(*_args: object, **_kwargs: object):
        raise RepositorySourceError("top-level config unreadable")
        yield  # pragma: no cover - keeps this a generator-shaped test double

    monkeypatch.setattr(checks_files, "iter_repository_python_files", fail_inventory)
    report = EnforcerReport(ok=True)
    checks_files.check_duplicate_config_roots(report, tmp_path, source_files=(runtime,))

    assert _kinds(report) == ["repository-source-inventory-error"]
    assert report.violations[0].path == "config"
    assert report.violations[0].message == "top-level config unreadable"


def test_empty_file_scan_covers_allowed_nonempty_empty_and_stat_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init = _write(tmp_path, "core/__init__.py", "")
    empty = _write(tmp_path, "core/empty.py", "")
    nonempty = _write(tmp_path, "core/nonempty.py")

    report = EnforcerReport(ok=True)
    checks_files.check_empty_non_init_files(report, tmp_path, source_files=(init, empty, nonempty))
    assert _kinds(report) == ["empty-production-file"]
    assert report.violations[0].path == "core/empty.py"

    original_stat = Path.stat

    def stat(path: Path, *args: object, **kwargs: object):
        if path == nonempty:
            raise OSError("denied")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    failure = EnforcerReport(ok=True)
    checks_files.check_empty_non_init_files(failure, tmp_path, source_files=(nonempty,))
    assert _kinds(failure) == ["filesystem-error"]


def test_file_checks_preserve_direct_inventory_compatibility(tmp_path: Path) -> None:
    _write(tmp_path, "core/config/settings.py")
    _write(tmp_path, "runtime/config/settings.py")
    _write(tmp_path, "core/empty.py", "")

    duplicates = EnforcerReport(ok=True)
    checks_files.check_duplicate_config_roots(duplicates, tmp_path)
    assert _kinds(duplicates) == ["config-duplication-risk"]

    empty = EnforcerReport(ok=True)
    checks_files.check_empty_non_init_files(empty, tmp_path)
    assert _kinds(empty) == ["empty-production-file"]
