from __future__ import annotations

from pathlib import Path

from scripts.ci.integrity import auditor
from scripts.ci.integrity.decision_authority_alias_scan import check_decision_authority_aliases


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


def test_shadow_decision_core_definition_is_p0(tmp_path: Path) -> None:
    path = tmp_path / "shadow.py"
    path.write_text(
        "class ShadowDecisionCore:\n"
        "    def decide(self, state):\n"
        "        return {'action': 'shadow'}\n",
        encoding="utf-8",
    )

    findings = _scan(path)

    assert [item.check_id for item in findings] == ["P0_DECISION_AUTHORITY_DEFINITION"]
    assert findings[0].severity == "P0"


def test_local_decision_engine_definition_is_p0_even_with_version_suffix(tmp_path: Path) -> None:
    path = tmp_path / "local_engine.py"
    path.write_text(
        "class LocalDecisionEngineV2:\n"
        "    def optimize(self, state):\n"
        "        return state\n",
        encoding="utf-8",
    )

    findings = _scan(path)

    assert [item.check_id for item in findings] == ["P0_DECISION_AUTHORITY_DEFINITION"]


def test_decision_core_contract_type_without_authority_methods_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "contract.py"
    path.write_text(
        "class DecisionCoreContract:\n"
        "    decision_owner = 'DecisionCore'\n",
        encoding="utf-8",
    )

    assert _scan(path) == []


def test_non_authoritative_runtime_service_alias_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "service_alias.py"
    path.write_text("RuntimeExecutionService = CanonicalRuntimeExecutionService\n", encoding="utf-8")

    assert _scan(path) == []


def test_snake_case_decision_core_instance_binding_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "instance_binding.py"
    path.write_text("decision_core = build_canonical_decision_core()\n", encoding="utf-8")

    assert _scan(path) == []


def test_existing_runtime_decision_core_tripwire_stays_fail_closed() -> None:
    path = Path("boot/runtime_service_contracts.py")

    findings = _scan(path)

    assert not [item for item in findings if "RuntimeDecisionCore" in item.message]


def test_canonical_integrity_auditor_keeps_single_owner_contract() -> None:
    assert callable(auditor.run_audit)
    assert callable(auditor.write_reports)
