from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.ci.integrity import auditor


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _spec() -> dict[str, Any]:
    return {
        "executable_decision_authority_names": ["DecisionCore", "DecisionEngine", "PlannerEngine"],
        "second_brain_suspicious_terms": ["second_brain", "strategy_engine"],
        "canonical_flow": ["signal", "state", "decision", "policy", "guard", "execution", "verification", "evidence", "archive"],
        "side_effect_calls": ["requests.get", "subprocess.run"],
        "approved_side_effect_roots": ["runtime/_internal/", "scripts/"],
        "admin_required_terms": ["capability", "risk", "evidence", "health"],
        "registry_required_terms": ["registry", "manifest", "policy", "guard"],
        "canonical_name_groups": [["tenant", "account", "business", "workspace"]],
        "canonical_name_alias_policy": {},
        "thresholds": {"fail_on_severity": ["P0"]},
    }


def test_integrity_auditor_helpers_and_file_iteration(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(auditor, "ROOT", tmp_path)

    _write(tmp_path / "core/ai/decision_core.py", "class DecisionCore:\n    pass\n")
    _write(tmp_path / "application/live.py", "VALUE = 1\n")
    _write(tmp_path / "reports/ignored.py", "VALUE = 2\n")
    _write(tmp_path / "target/ignored.py", "VALUE = 3\n")
    _write(tmp_path / "application/bad_syntax.py", "def broken(:\n")

    files = [path.relative_to(tmp_path).as_posix() for path in auditor.iter_python_files()]

    assert "application/live.py" in files
    assert "reports/ignored.py" not in files
    assert "target/ignored.py" not in files
    assert auditor.rel(tmp_path / "application/live.py") == "application/live.py"
    assert auditor.parse_file(tmp_path / "application/live.py") is not None
    assert auditor.parse_file(tmp_path / "application/bad_syntax.py") is None

    index = auditor.collect_text_index([tmp_path / "application/live.py"])
    assert index["application/live.py"] == "VALUE = 1\n"

    finding = auditor.finding("CHECK", "P1", "Title", tmp_path / "application/live.py", 1, "message", "recommendation")
    assert finding.path == "application/live.py"


def test_integrity_auditor_individual_checks_emit_expected_findings(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(auditor, "ROOT", tmp_path)

    _write(tmp_path / "core/ai/decision_core.py", "class DecisionCore:\n    pass\n")
    _write(
        tmp_path / "application/rogue.py",
        "import requests\n"
        "class DecisionEngine:\n"
        "    pass\n"
        "def run():\n"
        "    return requests.get('https://example.test')\n",
    )
    _write(tmp_path / "application/second_brain_surface.py", "VALUE = 1\n")
    _write(tmp_path / "interfaces/bad_import.py", "from runtime.boot import env\n")
    _write(tmp_path / "docs/text.py", "tenant account business\n")

    files = auditor.iter_python_files()
    spec = _spec()

    single = auditor.check_single_decision_core(files, spec)
    no_second = auditor.check_no_second_brain(files, spec)
    side_effects = auditor.check_runtime_side_effects(files, spec)
    imports = auditor.check_import_boundaries(files)
    flow = auditor.check_canonical_flow(files, spec)
    admin = auditor.check_admin_surface(files, spec)
    registry = auditor.check_registry_contracts(files, spec)
    evidence = auditor.check_evidence_replay_config(files)
    naming = auditor.check_naming_synonyms(files, spec)

    assert any(item.check_id == "P0_SINGLE_DECISION_CORE" for item in single)
    assert any(item.check_id == "P0_NO_SECOND_BRAIN" for item in no_second)
    assert any(item.check_id == "P1_RUNTIME_SIDE_EFFECTS" for item in side_effects)
    assert any(item.check_id == "P1_IMPORT_BOUNDARY" for item in imports)
    assert any(item.check_id == "P1_CANONICAL_FLOW" for item in flow)
    assert any(item.check_id == "P1_ADMIN_SURFACE" for item in admin)
    assert any(item.check_id == "P1_REGISTRY_COMPLETENESS" for item in registry)
    assert any(item.severity == "P2" for item in evidence)
    assert any(item.check_id == "P1_NAMING_SYNONYMS" for item in naming)


def test_integrity_auditor_documented_aliases_close_naming_findings(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(auditor, "ROOT", tmp_path)

    _write(tmp_path / "docs/names.py", "tenant account business workspace\n")

    spec = _spec()
    assert auditor.check_naming_synonyms(auditor.iter_python_files(), spec)

    spec["canonical_name_alias_policy"] = {
        "tenant": {
            "canonical": "tenant",
            "aliases": ["account", "business", "workspace"],
            "reason": "documented product aliases",
        }
    }

    assert auditor._documented_alias_groups(spec) == {("account", "business", "tenant", "workspace")}
    assert auditor.check_naming_synonyms(auditor.iter_python_files(), spec) == []


def test_integrity_auditor_scoring_and_reports(tmp_path: Path, monkeypatch: Any) -> None:
    json_report = tmp_path / "reports/integrity.json"
    markdown_report = tmp_path / "reports/integrity.md"

    monkeypatch.setattr(auditor, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(auditor, "JSON_REPORT", json_report)
    monkeypatch.setattr(auditor, "MARKDOWN_REPORT", markdown_report)

    @dataclass(frozen=True)
    class DummyInventory:
        total_test_files: int = 3
        all_tests_gate_present: bool = True
        pytest_root: str = "tests"

    @dataclass(frozen=True)
    class DummyRisk:
        risk_id: str = "risk"
        status: str = "covered"
        test_files_found: tuple[str, ...] = ("tests/unit/test_x.py",)
        active_gates: tuple[str, ...] = ("fast",)
        active_steps: tuple[str, ...] = ("unit-tests",)

    class DummyIndex:
        inventory = DummyInventory()
        risks = (DummyRisk(),)

        def to_json(self) -> dict[str, object]:
            return {"dummy": True}

    monkeypatch.setattr(auditor, "build_active_test_index", lambda: DummyIndex())

    findings = [
        auditor.Finding("P0_SINGLE_DECISION_CORE", "P0", "title", "path.py", 1, "message", "recommendation"),
        auditor.Finding("P1_ADMIN_SURFACE", "P1", "title", "path.py", 2, "message", "recommendation"),
        auditor.Finding("P2_EVIDENCE_COVERAGE", "P2", "title", "path.py", 3, "message", "recommendation"),
    ]
    summary = auditor.summarize(findings)
    card = auditor.score(findings, _spec())
    report = auditor.IntegrityReport(ok=False, scorecard=card, findings=findings, summary=summary)

    assert summary == {"P0": 1, "P1": 1, "P2": 1}
    assert card.second_brain_risk in {"low", "medium", "high"}

    auditor.write_reports(report)

    assert json_report.exists()
    assert markdown_report.exists()
    assert "BusinessAIOS Integrity Auditor" in markdown_report.read_text(encoding="utf-8")
    assert "active_test_index" in json_report.read_text(encoding="utf-8")


def test_integrity_auditor_main_uses_report_result(monkeypatch: Any) -> None:
    report = auditor.IntegrityReport(
        ok=True,
        scorecard=auditor.ScoreCard(100, 100, "low", 100, 100, 100, 100),
        findings=[],
        summary={"P0": 0, "P1": 0, "P2": 0},
    )
    written: list[bool] = []

    monkeypatch.setattr(auditor, "run_audit", lambda: report)
    monkeypatch.setattr(auditor, "write_reports", lambda _report: written.append(True))

    assert auditor.main() == 0
    assert written == [True]
