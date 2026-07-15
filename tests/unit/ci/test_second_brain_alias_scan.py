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


def test_abstract_decision_core_port_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "port.py"
    path.write_text(
        "from abc import ABC, abstractmethod\n"
        "class DecisionCorePort(ABC):\n"
        "    @abstractmethod\n"
        "    def decide(self, state):\n"
        "        ...\n",
        encoding="utf-8",
    )

    assert _scan(path) == []


def test_protocol_style_decision_core_contract_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "protocol.py"
    path.write_text(
        "class DecisionCoreProtocol:\n"
        "    def decide(self, state):\n"
        "        raise NotImplementedError\n",
        encoding="utf-8",
    )

    assert _scan(path) == []


def test_concrete_decision_core_port_is_still_p0(tmp_path: Path) -> None:
    path = tmp_path / "fake_port.py"
    path.write_text(
        "class DecisionCorePort:\n"
        "    def decide(self, state):\n"
        "        return {'action': 'hidden'}\n",
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


def test_literal_canon_markers_are_not_executable_aliases(tmp_path: Path) -> None:
    path = tmp_path / "markers.py"
    path.write_text(
        "CANON_BUILD_DECISION_CORE_COMPAT_WRAPPER = True\n"
        "CANON_RUNTIME_DECISION_CORE_NAME_RESERVED = 'DecisionCore'\n",
        encoding="utf-8",
    )

    assert _scan(path) == []


def test_non_authoritative_decision_core_lifecycle_helpers_are_allowed(tmp_path: Path) -> None:
    path = tmp_path / "helpers.py"
    path.write_text(
        "def validate_headless_decision_core(value):\n"
        "    return value is not None\n"
        "def build_decision_core():\n"
        "    return build_runtime_execution_service()\n"
        "def register_decision_core(registry):\n"
        "    return register_runtime_execution_service(registry)\n",
        encoding="utf-8",
    )

    assert _scan(path) == []


def test_canon_named_callable_alias_is_still_p0(tmp_path: Path) -> None:
    path = tmp_path / "callable_marker.py"
    path.write_text(
        "CANON_RUNTIME_DECISION_CORE = RuntimeDecisionExecutionService\n",
        encoding="utf-8",
    )

    findings = _scan(path)

    assert [item.check_id for item in findings] == ["P0_DECISION_AUTHORITY_ALIAS"]


def test_snake_case_shadow_decision_core_function_is_p0(tmp_path: Path) -> None:
    path = tmp_path / "shadow_function.py"
    path.write_text(
        "def shadow_decision_core(state):\n"
        "    return {'action': 'shadow'}\n",
        encoding="utf-8",
    )

    findings = _scan(path)

    assert [item.check_id for item in findings] == ["P0_DECISION_AUTHORITY_DEFINITION"]


def test_constant_import_alias_is_not_executable(tmp_path: Path) -> None:
    path = tmp_path / "constant_import.py"
    path.write_text(
        "from core.decision_core_contract import "
        "CANONICAL_DECISION_CORE_PATH as CANON_DECISION_CORE_PATH\n",
        encoding="utf-8",
    )

    assert _scan(path) == []


def test_existing_runtime_decision_core_tripwire_stays_fail_closed() -> None:
    path = Path("boot/runtime_service_contracts.py")

    findings = _scan(path)

    assert not [item for item in findings if "RuntimeDecisionCore" in item.message]


def test_canonical_integrity_auditor_keeps_single_owner_contract() -> None:
    assert callable(auditor.run_audit)
    assert callable(auditor.write_reports)
