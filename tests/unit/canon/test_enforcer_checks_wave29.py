from __future__ import annotations

from pathlib import Path

import pytest

import canon.enforcer.checks_ast as checks_ast
import canon.enforcer.checks_files as checks_files
import canon.enforcer.checks_invariants as checks_invariants
from canon.enforcer.reporting import EnforcerReport
from canon.repository_sources import RepositorySourceError


def _write(root: Path, relative: str, text: str = "x = 1\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _kinds(report: EnforcerReport) -> list[str]:
    return [item.kind for item in report.violations]


def test_ast_checks_cover_fail_closed_and_all_architecture_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_utf = _write(tmp_path, "core/unreadable.py")
    syntax = _write(tmp_path, "core/syntax.py", "def broken(:\n")
    core = _write(
        tmp_path,
        "core/risky.py",
        """import requests
from subprocess import run
threshold = 1.5
provider.client.post()
connector.call()
def f():
    pass
""",
    )
    critical = _write(tmp_path, "runtime/critical.py", "try:\n    x = 1\nexcept Exception:\n        pass\n")
    runtime = _write(
        tmp_path,
        "runtime/decider.py",
        "def choose_offer():\n    return 1\nservice.choose_strategy()\n",
    )
    interface_stub = _write(tmp_path, "interfaces/send.py", "def send():\n    pass\n")
    interface_todo = _write(tmp_path, "interfaces/todo.py", "# TODO wire\ndef ready():\n    return 1\n")
    safe = _write(tmp_path, "interfaces/safe.py", "def ready():\n    return 1\n")

    original = checks_ast.safe_read_text

    def read(path: Path) -> str:
        if path == bad_utf:
            raise RepositorySourceError("bad utf")
        return original(path)

    monkeypatch.setattr(checks_ast, "safe_read_text", read)
    monkeypatch.setattr(checks_ast, "GOD_MODULE_LINE_THRESHOLD", 2)
    monkeypatch.setattr(checks_ast, "GOD_MODULE_FUNC_THRESHOLD", 0)
    monkeypatch.setattr(checks_ast, "GOD_MODULE_IMPORT_THRESHOLD", 0)

    report = EnforcerReport(ok=True)
    paths = (bad_utf, syntax, core, critical, runtime, interface_stub, interface_todo, safe)
    checks_ast.check_ast_semantics(report, tmp_path, source_files=paths)
    kinds = _kinds(report)
    expected = {
        "unreadable-python-source",
        "syntax-error",
        "god-module-risk",
        "silent-failure",
        "fake-ready-integration",
        "hidden-business-logic",
        "core-side-effect-import",
        "core-side-effect-call",
        "core-infra-call",
        "runtime-decision-logic",
        "runtime-decision-call",
    }
    assert expected <= set(kinds)
    assert any(item.path == "core/risky.py" for item in report.violations)

    # Also exercise the public no-precomputed-inventory compatibility path.
    clean_report = EnforcerReport(ok=True)
    checks_ast.check_ast_semantics(clean_report, tmp_path)
    assert "syntax-error" in _kinds(clean_report)


def test_file_checks_use_one_inventory_and_fail_closed_on_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = _write(tmp_path, "core/empty.py", "")
    init = _write(tmp_path, "core/__init__.py", "")
    first = _write(tmp_path, "core/config/settings.py")
    second = _write(tmp_path, "runtime/config/settings.py")
    nonconfig = _write(tmp_path, "core/other.py")

    report = EnforcerReport(ok=True)
    paths = (empty, init, first, second, nonconfig)
    checks_files.check_empty_non_init_files(report, tmp_path, source_files=paths)
    checks_files.check_duplicate_config_roots(report, tmp_path, source_files=paths)
    assert _kinds(report).count("empty-production-file") == 1
    assert _kinds(report).count("config-duplication-risk") == 1

    original_stat = Path.stat

    def stat(path: Path, *args: object, **kwargs: object):
        if path == nonconfig:
            raise OSError("denied")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    failure = EnforcerReport(ok=True)
    checks_files.check_empty_non_init_files(failure, tmp_path, source_files=(nonconfig,))
    assert _kinds(failure) == ["filesystem-error"]
    monkeypatch.setattr(Path, "stat", original_stat)

    # Compatibility path without a precomputed inventory.
    direct = EnforcerReport(ok=True)
    checks_files.check_duplicate_config_roots(direct, tmp_path)
    assert "config-duplication-risk" in _kinds(direct)


def test_invariant_checks_preserve_roles_and_detect_second_brains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = EnforcerReport(ok=True)
    checks_invariants.check_required_invariants(report, tmp_path)
    assert _kinds(report).count("missing-invariant") == 5

    second = _write(tmp_path, "core/decision_engine.py")
    normal = _write(tmp_path, "core/normal.py")
    report = EnforcerReport(ok=True)
    checks_invariants.check_second_brain_file_hints(report, tmp_path, source_files=(second, normal))
    assert _kinds(report) == ["second-brain-file"]

    left = _write(tmp_path, "core/policy/a.py")
    right = _write(tmp_path, "core/policies/b.py")
    report = EnforcerReport(ok=True)
    checks_invariants.check_synonym_namespaces(report, tmp_path, source_files=(left, right))
    assert report.violations[0].severity == "high"

    (tmp_path / "core/policy/CANON_NAMESPACE_ROLE.md").write_text("left", encoding="utf-8")
    (tmp_path / "core/policies/CANON_NAMESPACE_ROLE.md").write_text("right", encoding="utf-8")
    distinct = EnforcerReport(ok=True)
    checks_invariants.check_synonym_namespaces(distinct, tmp_path, source_files=(left, right))
    assert distinct.violations == []

    monkeypatch.setattr(
        checks_invariants,
        "read_utf8_source",
        lambda _path: (_ for _ in ()).throw(RepositorySourceError("unreadable role")),
    )
    unreadable = EnforcerReport(ok=True)
    checks_invariants.check_synonym_namespaces(unreadable, tmp_path, source_files=(left, right))
    assert _kinds(unreadable).count("unreadable-namespace-role") == 2
    assert "synonym-namespace" in _kinds(unreadable)

    # Zero-sided namespace and public compatibility inventory paths.
    (tmp_path / "runtime/read_models").mkdir(parents=True)
    (tmp_path / "core/read_model").mkdir(parents=True)
    zero = EnforcerReport(ok=True)
    checks_invariants.check_synonym_namespaces(zero, tmp_path, source_files=(left, right))
    direct = EnforcerReport(ok=True)
    checks_invariants.check_second_brain_file_hints(direct, tmp_path)
    assert "second-brain-file" in _kinds(direct)


def test_ast_checks_cover_safe_negative_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    core = _write(
        tmp_path,
        "core/safe.py",
        "import math\nfrom pathlib import Path\nmath.sqrt(4)\nplain.post()\n",
    )
    runtime = _write(tmp_path, "runtime/safe.py", "service.observe()\n")
    monkeypatch.setattr(checks_ast, "GOD_MODULE_LINE_THRESHOLD", 999)
    monkeypatch.setattr(checks_ast, "GOD_MODULE_FUNC_THRESHOLD", 999)
    monkeypatch.setattr(checks_ast, "GOD_MODULE_IMPORT_THRESHOLD", 999)
    report = EnforcerReport(ok=True)
    checks_ast.check_ast_semantics(report, tmp_path, source_files=(core, runtime))
    assert report.violations == []


def test_required_invariants_accept_complete_canonical_layout(tmp_path: Path) -> None:
    _write(tmp_path, "core/ai/decision_core.py")
    _write(tmp_path, "runtime/executor.py")
    _write(tmp_path, "runtime/guard.py")
    (tmp_path / "runtime/platform").mkdir(parents=True)
    (tmp_path / "interfaces").mkdir()
    report = EnforcerReport(ok=True)
    checks_invariants.check_required_invariants(report, tmp_path)
    assert report.violations == []
