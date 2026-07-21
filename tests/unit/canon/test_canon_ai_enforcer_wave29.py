from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

import canon.canon_ai_enforcer as enforcer
from canon.enforcer.reporting import EnforcerReport
from canon.repository_sources import RepositorySourceError


def test_run_enforcer_fails_closed_for_invalid_root(tmp_path: Path) -> None:
    report = enforcer.run_enforcer(tmp_path / "missing")
    assert report.ok is False
    assert [item.kind for item in report.violations] == ["invalid-repository-root"]


def test_run_enforcer_materializes_one_inventory_and_shares_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "core" / "a.py"
    source.parent.mkdir(parents=True)
    source.write_text("x = 1\n", encoding="utf-8")
    calls: list[tuple[str, tuple[Path, ...] | None]] = []

    monkeypatch.setattr(enforcer, "check_required_invariants", lambda report, root: calls.append(("required", None)))
    monkeypatch.setattr(enforcer, "check_readme_and_contributing", lambda report, root: calls.append(("docs", None)))
    monkeypatch.setattr(
        enforcer,
        "check_super_canon_world_model_contract",
        lambda report, root: calls.append(("world", None)),
    )
    monkeypatch.setattr(enforcer, "iter_py_files", lambda root: iter((source,)))

    def capture(name: str):
        def inner(report, root, *, source_files):
            calls.append((name, source_files))
        return inner

    monkeypatch.setattr(enforcer, "check_second_brain_file_hints", capture("brain"))
    monkeypatch.setattr(enforcer, "check_synonym_namespaces", capture("synonyms"))
    monkeypatch.setattr(enforcer, "check_empty_non_init_files", capture("empty"))
    monkeypatch.setattr(enforcer, "check_duplicate_config_roots", capture("config"))
    monkeypatch.setattr(enforcer, "check_ast_semantics", capture("ast"))

    report = enforcer.run_enforcer(tmp_path)
    assert report.ok is True
    inventories = [value for name, value in calls if name in {"brain", "synonyms", "empty", "config", "ast"}]
    assert inventories == [(source,)] * 5


def test_run_enforcer_reports_inventory_failure_but_keeps_non_source_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(enforcer, "check_required_invariants", lambda *_args: None)
    monkeypatch.setattr(enforcer, "check_readme_and_contributing", lambda *_args: None)
    monkeypatch.setattr(enforcer, "check_super_canon_world_model_contract", lambda *_args: None)
    monkeypatch.setattr(
        enforcer,
        "iter_py_files",
        lambda _root: (_ for _ in ()).throw(RepositorySourceError("walk denied")),
    )
    report = enforcer.run_enforcer(tmp_path)
    assert report.ok is False
    assert [item.kind for item in report.violations] == ["repository-source-inventory-error"]


def test_main_preserves_text_and_exit_contract(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ok_report = EnforcerReport(ok=True)
    monkeypatch.setattr(enforcer, "run_enforcer", lambda _root: ok_report)
    assert enforcer.main() == 0
    output = capsys.readouterr().out
    assert "CANON ENFORCER: no violations found." in output
    assert "JSON REPORT:" in output

    failed = EnforcerReport(ok=False)
    failed.add(severity="critical", kind="bad", path="x.py", line=2, message="broken", hint=None)
    monkeypatch.setattr(enforcer, "run_enforcer", lambda _root: failed)
    assert enforcer.main() == 1
    output = capsys.readouterr().out
    assert "[CRITICAL] bad @ x.py:2" in output


def test_module_entrypoint_raises_system_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "canon.canon_ai_enforcer", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("canon.canon_ai_enforcer", run_name="__main__")
    assert exc_info.value.code == 1
