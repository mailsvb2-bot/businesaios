from __future__ import annotations

from pathlib import Path

from scripts.ci.fs import ensure_writable_dir


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifacts_dir() -> Path:
    return ensure_writable_dir(repo_root() / "artifacts")


def reports_dir() -> Path:
    return ensure_writable_dir(artifacts_dir() / "ci")


def _report_subdir(name: str) -> Path:
    return ensure_writable_dir(reports_dir() / name)


def junit_dir() -> Path:
    return _report_subdir("junit")


def execution_dir() -> Path:
    return _report_subdir("execution")


def coverage_dir() -> Path:
    return _report_subdir("coverage")


def summaries_dir() -> Path:
    return _report_subdir("summaries")


def dist_dir() -> Path:
    return ensure_writable_dir(repo_root() / "dist")


def hooks_dir() -> Path:
    return repo_root() / ".githooks"
