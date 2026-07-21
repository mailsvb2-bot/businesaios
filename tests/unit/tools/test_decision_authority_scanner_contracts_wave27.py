from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest

import tools.decision_authority_indirect_scanner as scanner
from tools.decision_authority_indirect_scanner import Finding


def _expr(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


def _call(source: str) -> ast.Call:
    return cast(ast.Call, _expr(source))



def test_root_validation_and_walk_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    assert scanner._validated_repo_root(str(root)) == root.resolve()

    with pytest.raises(ValueError, match="path"):
        scanner._validated_repo_root(cast(object, 7))
    with pytest.raises(ValueError, match="exist"):
        scanner._validated_repo_root(root / "missing")
    file_root = root / "file.txt"
    file_root.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="directory"):
        scanner._validated_repo_root(file_root)

    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "not_python.txt").write_text("x", encoding="utf-8")
    (root / "directory.py").mkdir()
    package = root / "package"
    package.mkdir()
    (package / "b.py").write_text("y = 2\n", encoding="utf-8")
    for name in (".hidden", ".venv", "artifacts"):
        directory = root / name
        directory.mkdir()
        (directory / "ignored.py").write_text("bad = 1\n", encoding="utf-8")

    symlinks_supported = True
    try:
        (root / "linked_dir").symlink_to(package, target_is_directory=True)
        (root / "linked_file.py").symlink_to(root / "a.py")
    except OSError:
        symlinks_supported = False

    found = [path.relative_to(root).as_posix() for path in scanner._iter_python_files(root)]
    assert found == ["a.py", "package/b.py"]
    if symlinks_supported:
        assert "linked_file.py" not in found

    def broken_walk(*_args: object, **kwargs: object):
        onerror = kwargs["onerror"]
        assert callable(onerror)
        onerror(OSError("denied"))
        yield from ()

    monkeypatch.setattr(scanner.os, "walk", broken_walk)
    with pytest.raises(RuntimeError, match="failed to walk"):
        list(scanner._iter_python_files(root))


def test_expression_and_authority_helpers_cover_static_dynamic_paths() -> None:
    aliases = {"dc": "core.ai.decision_core", "ga": "getattr"}
    assert Finding("c", "x.py", 3, "d").format() == "x.py:3: c: d"

    assert scanner._static_string(ast.Constant("x")) == "x"
    assert scanner._static_string(ast.Constant(1)) is None
    assert scanner._static_string(_expr("f'abc'")) == "abc"
    assert scanner._static_string(_expr("f'{name}'")) is None
    assert scanner._static_string(ast.JoinedStr(values=[ast.Constant(1)])) is None
    assert scanner._static_string(_expr("'a' + 'b'")) == "ab"
    assert scanner._static_string(_expr("'a' + name")) is None
    assert scanner._static_string(_expr("name")) is None

    assert scanner._qualified_name(_expr("dc"), aliases) == "core.ai.decision_core"
    assert scanner._qualified_name(_expr("dc.DecisionCore"), aliases).endswith(".DecisionCore")
    assert scanner._qualified_name(_expr("factory()"), aliases) == ""

    assert scanner._expression_path(_expr("dc"), aliases) == "core.ai.decision_core"
    assert scanner._expression_path(_expr("dc.engine"), aliases).endswith(".engine")
    assert scanner._expression_path(_expr("ga(dc, 'decide')"), aliases) == "getattr(core.ai.decision_core)"
    assert scanner._expression_path(_expr("factory('literal')"), aliases) == "factory('literal')"
    assert scanner._expression_path(_expr("factory(dc)"), aliases).startswith("factory(")
    assert scanner._expression_path(_expr("factory()"), aliases) == "factory()"
    assert scanner._expression_path(_expr("dc.__dict__['decide']"), aliases).endswith("['decide']")
    assert scanner._expression_path(_expr("dc.__dict__[key]"), aliases).endswith("[]")
    assert scanner._expression_path(_expr("1 + 2"), aliases) == ""

    assert scanner._call_name(_expr("dc.decide"), aliases) == ("core.ai.decision_core", "decide")
    assert scanner._call_name(_expr("dc"), aliases) == ("core.ai", "decision_core")
    assert scanner._call_name(_expr("plain"), {}) == (None, "plain")
    assert scanner._call_name(_expr("factory()"), {}) == (None, None)

    assert scanner._normalized_receiver("Decision_Core[0]") == "decisioncore0"
    assert scanner._receiver_looks_like_authority("service") is False
    assert scanner._receiver_looks_like_authority("decision_service") is True
    assert scanner._is_authority_access(None, "unknown") is False
    assert scanner._is_authority_access(None, "decide") is True
    assert scanner._is_authority_access("certificate", "issue") is False
    assert scanner._is_authority_access("decision_engine", "issue") is True

    tree = ast.parse("result = core.decide()")
    attr = next(node for node in ast.walk(tree) if isinstance(node, ast.Attribute))
    name = next(node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == "core")
    parents = scanner._parent_map(tree)
    assert scanner._is_direct_call_function(attr, parents) is True
    assert scanner._is_direct_call_function(name, parents) is False

    target = ast.parse("a, *b = values").body[0].targets[0]  # type: ignore[attr-defined]
    assert scanner._bound_names_in_target(target) == {"a", "b"}
