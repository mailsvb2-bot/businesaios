from __future__ import annotations

from pathlib import Path

from scripts.ci.fs import ensure_writable_dir


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifacts_dir() -> Path:
    path = repo_root() / "artifacts"
    return ensure_writable_dir(path)


def reports_dir() -> Path:
    path = artifacts_dir() / "ci"
    return ensure_writable_dir(path)


def junit_dir() -> Path:
    path = reports_dir() / "junit"
    return ensure_writable_dir(path)



def execution_dir() -> Path:
    path = reports_dir() / "execution"
    return ensure_writable_dir(path)

def coverage_dir() -> Path:
    path = reports_dir() / "coverage"
    return ensure_writable_dir(path)


def summaries_dir() -> Path:
    path = reports_dir() / "summaries"
    return ensure_writable_dir(path)


def dist_dir() -> Path:
    path = repo_root() / "dist"
    return ensure_writable_dir(path)


def hooks_dir() -> Path:
    path = repo_root() / ".githooks"
    return ensure_writable_dir(path)
