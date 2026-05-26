from __future__ import annotations

import json

from tools.project_tree import build_project_tree, render_project_tree_json, render_project_tree_text


def test_project_tree_renders_clean_text_tree(tmp_path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "runtime.sqlite3").write_text("ignored\n", encoding="utf-8")

    result = build_project_tree(tmp_path, max_depth=2)
    rendered = render_project_tree_text(result)

    assert "app/" in rendered
    assert "main.py" in rendered
    assert ".git" not in rendered
    assert "runtime.sqlite3" not in rendered
    assert "summary:" in rendered
    assert result.summary.skipped == 2


def test_project_tree_json_contains_summary_and_tree(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("hello\n", encoding="utf-8")

    payload = json.loads(render_project_tree_json(build_project_tree(tmp_path, max_depth=1)))

    assert payload["summary"]["files"] == 0
    assert payload["summary"]["directories"] == 2
    assert payload["tree"]["kind"] == "directory"
    assert payload["tree"]["children"][0]["name"] == "docs"


def test_project_tree_dirs_only_omits_files(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("x = 1\n", encoding="utf-8")

    result = build_project_tree(tmp_path, max_depth=3, include_files=False)
    rendered = render_project_tree_text(result)

    assert "src/" in rendered
    assert "module.py" not in rendered
    assert result.summary.files == 0


def test_project_tree_extra_exclude_pattern(tmp_path) -> None:
    (tmp_path / "keep").mkdir()
    (tmp_path / "drop-me").mkdir()

    result = build_project_tree(tmp_path, extra_excludes=("drop-*",))
    rendered = render_project_tree_text(result)

    assert "keep/" in rendered
    assert "drop-me" not in rendered
    assert result.summary.skipped == 1
