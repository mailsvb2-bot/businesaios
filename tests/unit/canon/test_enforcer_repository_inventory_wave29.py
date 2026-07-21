from __future__ import annotations

import os
from pathlib import Path

import pytest

import canon.repository_sources as sources
from canon.enforcer import rules


def _write(root: Path, relative: str, text: str = "x = 1\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_repository_inventory_validates_filters_and_reads_strict_utf8(tmp_path: Path) -> None:
    core = _write(tmp_path, "core/a.py")
    runtime = _write(tmp_path, "runtime/platform/b.py")
    _write(tmp_path, "interfaces/c.py")
    _write(tmp_path, "other/d.py")
    _write(tmp_path, ".hidden/e.py")
    _write(tmp_path, "build/f.py")
    (tmp_path / "runtime" / "link").symlink_to(tmp_path / "other", target_is_directory=True)

    assert sources.validate_repository_root(str(tmp_path)) == tmp_path.resolve()
    with pytest.raises(ValueError, match="must be a path"):
        sources.validate_repository_root(3)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must exist"):
        sources.validate_repository_root(tmp_path / "missing")
    file_root = _write(tmp_path, "file-root.txt", "x")
    with pytest.raises(ValueError, match="must be a directory"):
        sources.validate_repository_root(file_root)

    selected = tuple(
        sources.iter_repository_python_files(
            tmp_path,
            included_prefixes=("runtime", "core\\"),
            excluded_prefixes=("runtime/platform", "", "core/nope"),
        )
    )
    assert selected == (core,)
    with pytest.raises(ValueError, match="must be strings"):
        tuple(sources.iter_repository_python_files(tmp_path, included_prefixes=(1,)))  # type: ignore[arg-type]

    all_paths = tuple(sources.iter_repository_python_files(tmp_path))
    assert core in all_paths and runtime in all_paths
    assert all(
        ".hidden" not in path.parts
        and "build" not in path.parts
        and "link" not in path.parts
        for path in all_paths
    )
    assert sources.read_utf8_source(core) == "x = 1\n"
    with pytest.raises(ValueError, match="must be a path"):
        sources.read_utf8_source("core/a.py")  # type: ignore[arg-type]

    broken = tmp_path / "core" / "broken.py"
    broken.write_bytes(b"\xff")
    with pytest.raises(sources.RepositorySourceError, match="failed to read UTF-8"):
        sources.read_utf8_source(broken)


def test_repository_inventory_fails_closed_on_walk_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_walk(*_args: object, **kwargs: object):
        onerror = kwargs["onerror"]
        onerror(OSError("denied"))  # type: ignore[operator]
        return iter(())

    monkeypatch.setattr(os, "walk", broken_walk)
    with pytest.raises(sources.RepositorySourceError, match="failed to walk"):
        tuple(sources.iter_repository_python_files(tmp_path))


def test_enforcer_rules_delegate_to_canonical_inventory(tmp_path: Path) -> None:
    core = _write(tmp_path, "core/a.py", "# TODO fix\n")
    runtime = _write(tmp_path, "runtime/platform/b.py")
    _write(tmp_path, "runtime.platform/wrong.py")
    _write(tmp_path, "other/ignored.py")
    _write(tmp_path, "core/__init__.py", "")

    assert tuple(rules.iter_py_files(tmp_path)) == (tmp_path / "core/__init__.py", core, runtime)
    assert rules.safe_read_text(core) == "# TODO fix\n"
    assert rules.path_str(Path("a\\b.py")) == "a\\b.py"
    assert rules.relative_path(tmp_path, runtime) == "runtime/platform/b.py"
    assert rules.is_under("runtime/platform/x.py", ("runtime",)) is True
    assert rules.is_under("corex/a.py", ("core",)) is False
    assert rules.is_critical_path("runtime/platform/b.py") is True
    assert rules.is_critical_path("interfaces/other.py") is False
    assert rules.nontrivial_py_count(tmp_path / "core") == 1
    assert rules.nontrivial_py_count(tmp_path / "missing") == 0
    assert list(rules.iter_todo_lines("# TODO one\n# noqa TODO ignored\nTODO two")) == [1, 3]


def test_relative_default_root_works_after_chdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _write(tmp_path, "core/a.py")
    monkeypatch.chdir(tmp_path)
    assert rules.relative_path(Path("."), source) == "core/a.py"
    assert tuple(rules.iter_py_files(Path("."))) == (source,)
