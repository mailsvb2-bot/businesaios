from __future__ import annotations

from pathlib import Path

from tools import typing_imports_codemod as codemod


def test_split_import_names_accepts_only_simple_typing_imports() -> None:
    assert codemod._split_import_names("from typing import Iterable, Mapping, Any") == [
        "Iterable",
        "Mapping",
        "Any",
    ]
    assert codemod._split_import_names("import typing") is None
    assert codemod._split_import_names("from typing import (Iterable)") is None
    assert codemod._split_import_names("from typing import Iterable  # comment") is None


def test_rewrite_text_moves_abc_names_and_preserves_typing_names() -> None:
    rewritten, moved = codemod._rewrite_text(
        "from typing import Any, Iterable, Mapping\n"
        "from typing import Optional\n"
        "VALUE = 1\n"
    )

    assert rewritten == (
        "from typing import Any\n"
        "from collections.abc import Iterable, Mapping\n"
        "from typing import Optional\n"
        "VALUE = 1\n"
    )
    assert moved == ("Iterable", "Mapping")


def test_iter_python_files_skips_virtualenv_and_cache_dirs(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/a.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv/ignored.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__/ignored.py").write_text("VALUE = 3\n", encoding="utf-8")

    files = sorted(path.relative_to(tmp_path).as_posix() for path in codemod._iter_python_files(tmp_path))

    assert files == ["pkg/a.py"]


def test_main_rewrites_scope_and_reports_changes(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = tmp_path / "repo"
    app = repo / "application"
    app.mkdir(parents=True)
    target = app / "sample.py"
    target.write_text("from typing import Any, Iterable\n", encoding="utf-8")

    monkeypatch.setattr(codemod, "REPO_ROOT", repo)

    assert codemod.main(["application"]) == 0

    assert target.read_text(encoding="utf-8") == (
        "from typing import Any\n"
        "from collections.abc import Iterable\n"
    )
    captured = capsys.readouterr()
    assert "application/sample.py: moved Iterable" in captured.out
    assert "changed_files=1" in captured.out


def test_main_rejects_missing_and_escaping_scopes(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(codemod, "REPO_ROOT", repo)

    assert codemod.main(["missing"]) == 2
    assert "scope does not exist: missing" in capsys.readouterr().err

    assert codemod.main(["../outside"]) == 2
    assert "scope escapes repository root: ../outside" in capsys.readouterr().err
