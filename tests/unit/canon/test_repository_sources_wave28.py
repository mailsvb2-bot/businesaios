from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

import canon.repository_sources as sources


def test_root_and_prefix_validation(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    assert sources.validate_repository_root(str(root)) == root.resolve()

    with pytest.raises(ValueError, match="path"):
        sources.validate_repository_root(cast(object, 3))
    with pytest.raises(ValueError, match="exist"):
        sources.validate_repository_root(root / "missing")
    file_root = root / "file.txt"
    file_root.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="directory"):
        sources.validate_repository_root(file_root)

    assert sources._normalized_prefixes(("/tests", "tests/", "", " runtime\\sandbox ")) == (
        "runtime/sandbox/",
        "tests/",
    )
    with pytest.raises(ValueError, match="strings"):
        sources._normalized_prefixes(cast(object, ("tests", 7)))


def test_inventory_is_deterministic_symlink_safe_and_configurable(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    for relative, text in {
        "z.py": "z = 1\n",
        "a.py": "a = 1\n",
        "not.txt": "ignored\n",
        "package/b.py": "b = 1\n",
        "tests/test_hidden.py": "bad = 1\n",
        ".hidden/hidden.py": "bad = 1\n",
        "artifacts/report.py": "bad = 1\n",
        "nested/node_modules/vendor.py": "bad = 1\n",
        "custom/skip.py": "bad = 1\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / "directory.py").mkdir()

    symlinks_supported = True
    try:
        (root / "linked.py").symlink_to(root / "a.py")
        (root / "linked_package").symlink_to(root / "package", target_is_directory=True)
    except OSError:
        symlinks_supported = False

    found = [
        path.relative_to(root).as_posix()
        for path in sources.iter_repository_python_files(
            root,
            excluded_prefixes=("tests",),
            excluded_dir_names=(*sources.DEFAULT_EXCLUDED_DIR_NAMES, "custom"),
        )
    ]
    assert found == ["a.py", "z.py", "package/b.py"]
    if symlinks_supported:
        assert "linked.py" not in found

    included_artifact = [
        path.relative_to(root).as_posix()
        for path in sources.iter_repository_python_files(
            root,
            root_excluded_dir_names=(),
        )
    ]
    assert "artifacts/report.py" in included_artifact


def test_inventory_and_read_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "ok.py"
    source.write_text("value = 1\n", encoding="utf-8")
    assert sources.read_utf8_source(source) == "value = 1\n"

    with pytest.raises(ValueError, match="path"):
        sources.read_utf8_source(cast(Path, "bad"))
    with pytest.raises(sources.RepositorySourceError, match="UTF-8"):
        sources.read_utf8_source(root / "missing.py")
    invalid = root / "invalid.py"
    invalid.write_bytes(b"\xff\xfe")
    with pytest.raises(sources.RepositorySourceError, match="UTF-8"):
        sources.read_utf8_source(invalid)

    def broken_walk(*_args: object, **kwargs: object):
        onerror = kwargs["onerror"]
        assert callable(onerror)
        onerror(OSError("denied"))
        yield from ()

    monkeypatch.setattr(os, "walk", broken_walk)
    with pytest.raises(sources.RepositorySourceError, match="walk"):
        list(sources.iter_repository_python_files(root))
