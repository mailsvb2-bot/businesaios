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



def test_scan_is_fail_closed_for_unreadable_parse_and_walk_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ok.py").write_text("value = 1\n", encoding="utf-8")
    (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    (root / "bytes.py").write_bytes(b"\xff\xfe")
    (root / "skip.py").write_text("decision_core.decide()\n", encoding="utf-8")

    original_owner = scanner.is_canonical_decision_owner_path
    monkeypatch.setattr(
        scanner, "is_canonical_decision_owner_path", lambda rel: rel == "skip.py" or original_owner(rel)
    )
    findings = scanner.scan(root)
    assert [item.code for item in findings] == [
        "decision_authority_unscannable_source",
        "decision_authority_unscannable_source",
    ]
    by_path = {item.path: item for item in findings}
    assert by_path["broken.py"].line == 1
    assert by_path["bytes.py"].line == 0

    duplicate = Finding("duplicate", "x.py", 1, "same")
    monkeypatch.setattr(scanner, "_iter_python_files", lambda _root: iter([root / "ok.py"]))
    monkeypatch.setattr(scanner, "_scan_ast", lambda **_kwargs: [duplicate, duplicate])
    assert scanner.scan(root) == (duplicate,)

    def broken_iter(_root: Path):
        raise RuntimeError("walk failed")
        yield  # pragma: no cover

    monkeypatch.setattr(scanner, "_iter_python_files", broken_iter)
    result = scanner.scan(root)
    assert result == (Finding("decision_authority_scan_error", ".", 0, "walk failed"),)


def test_main_preserves_cli_contract_and_bounds_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(scanner.Path, "cwd", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(scanner, "scan", lambda _root: ())
    assert scanner.main() == 0
    assert capsys.readouterr().out == "decision authority indirect scan passed\n"

    monkeypatch.setattr(scanner, "scan", lambda _root: (Finding("code", "one.py", 1, "detail"),))
    assert scanner.main() == 1
    single_output = capsys.readouterr().out
    assert "findings=1" in single_output
    assert "more finding" not in single_output

    many = tuple(Finding("code", f"{index:03}.py", index, "detail") for index in range(81))
    monkeypatch.setattr(scanner, "scan", lambda _root: many)
    assert scanner.main() == 1
    output = capsys.readouterr().out
    assert "findings=81" in output
    assert "... 1 more finding(s)" in output
    assert "080.py" not in output

    def invalid(_root: Path):
        raise ValueError("scan root must exist")

    monkeypatch.setattr(scanner, "scan", invalid)
    assert scanner.main() == 1
    assert capsys.readouterr().out.endswith("scan root must exist\n")


def test_module_entrypoint_raises_system_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import runpy

    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(scanner.__file__, run_name="__main__")
    assert exc_info.value.code == 0
