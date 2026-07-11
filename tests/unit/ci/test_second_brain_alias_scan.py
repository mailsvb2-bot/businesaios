from __future__ import annotations

from pathlib import Path

from scripts.ci.integrity import auditor
from scripts.ci.integrity.second_brain_alias_scan import check_decision_authority_aliases


def _scan(path: Path) -> list[auditor.Finding]:
    return check_decision_authority_aliases([path], auditor.load_spec())


def test_assignment_alias_to_runtime_decision_core_is_p0(tmp_path: Path) -> None:
    path = tmp_path / "runtime_alias.py"
    path.write_text("RuntimeDecisionCore = RuntimeDecisionExecutionService\n", encoding="utf-8")

    findings = _scan(path)

    assert [item.check_id for item in findings] == ["P0_DECISION_AUTHORITY_ALIAS"]
    assert findings[0].severity == "P0"


def test_import_alias_to_decision_engine_is_p0(tmp_path: Path) -> None:
    path = tmp_path / "import_alias.py"
    path.write_text("from core.ai.decision_core import DecisionCore as DecisionEngine\n", encoding="utf-8")

    findings = _scan(path)

    assert [item.check_id for item in findings] == ["P0_DECISION_AUTHORITY_ALIAS"]
    assert "DecisionCore as DecisionEngine" in findings[0].message


def test_non_authoritative_runtime_service_alias_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "service_alias.py"
    path.write_text("RuntimeExecutionService = CanonicalRuntimeExecutionService\n", encoding="utf-8")

    assert _scan(path) == []


def test_snake_case_decision_core_instance_binding_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "instance_binding.py"
    path.write_text("decision_core = build_canonical_decision_core()\n", encoding="utf-8")

    assert _scan(path) == []


def test_canonical_integrity_runner_exports_restored_contract() -> None:
    from scripts.ci.integrity import runner

    assert runner.CANON_INTEGRITY_AUDITOR_RUNNER is True
    assert callable(runner.run_audit)
    assert callable(runner.write_reports)
