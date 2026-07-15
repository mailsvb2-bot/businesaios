from __future__ import annotations

from pathlib import Path

from scripts.ci.integrity import auditor
from scripts.ci.integrity.decision_authority_alias_scan import check_decision_authority_aliases


def _scan(path: Path) -> list[auditor.Finding]:
    return check_decision_authority_aliases([path], auditor.load_spec())


def _scan_repo_source(
    *,
    tmp_path: Path,
    monkeypatch,
    relative: str,
    source: str,
) -> list[auditor.Finding]:
    root = tmp_path / "repo"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(auditor, "ROOT", root)
    return _scan(path)


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


def test_explicit_data_bindings_require_proven_non_executable_values(tmp_path: Path) -> None:
    path = tmp_path / "data_bindings.py"
    path.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True)\n"
        "class SynonymEntity:\n"
        "    canonical: str\n"
        "    synonyms: tuple[str, ...]\n"
        "RUNTIME_DECISION_EXECUTION_SERVICE_DEPS = ('registry',)\n"
        "DECISION_CORE_DEPS = RUNTIME_DECISION_EXECUTION_SERVICE_DEPS\n"
        "DECISION_CORE_SYNONYMS = SynonymEntity('DecisionCore', ('brain',))\n"
        "CANONICAL_DECISION_CORE_IMPORT_PATH = 'core.ai.decision_core.DecisionCore'\n"
        "CANON_DECISION_CORE_IMPORT_PATH = CANONICAL_DECISION_CORE_IMPORT_PATH\n",
        encoding="utf-8",
    )

    assert _scan(path) == []


def test_data_suffix_cannot_hide_an_executable_authority(tmp_path: Path) -> None:
    path = tmp_path / "false_data_bindings.py"
    path.write_text(
        "DECISION_CORE_DEPS = RuntimeDecisionCore\n"
        "DECISION_CORE_SYNONYMS = RuntimeDecisionCore()\n"
        "CANON_DECISION_CORE_IMPORT_PATH = RuntimeDecisionCore\n",
        encoding="utf-8",
    )

    findings = _scan(path)

    assert [item.check_id for item in findings] == ["P0_DECISION_AUTHORITY_ALIAS"] * 3


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


def test_typed_registry_reference_accessor_is_not_a_decision_issuer(tmp_path: Path) -> None:
    path = tmp_path / "registry_accessor.py"
    path.write_text(
        "class RuntimeTypedAccess:\n"
        "    def decision_core(self):\n"
        "        return self.registry.get(RuntimeServiceName.DECISION_CORE)\n",
        encoding="utf-8",
    )

    assert _scan(path) == []


def test_decision_core_callable_must_be_an_exact_reference_accessor(tmp_path: Path) -> None:
    path = tmp_path / "executable_accessors.py"
    path.write_text(
        "def decision_core():\n"
        "    return RuntimeDecisionCore()\n"
        "class RuntimeTypedAccess:\n"
        "    def decision_core(self):\n"
        "        return self.registry.get(RuntimeServiceName.DECISION_CORE).decide()\n",
        encoding="utf-8",
    )

    findings = _scan(path)

    assert [item.check_id for item in findings] == ["P0_DECISION_AUTHORITY_DEFINITION"] * 2


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


def test_canonical_singleton_storage_is_path_guard_and_value_bound(
    tmp_path: Path,
    monkeypatch,
) -> None:
    safe = (
        "_DECISION_CORE_SINGLETON = None\n"
        "def set_decision_core_singleton(core):\n"
        "    global _DECISION_CORE_SINGLETON\n"
        "    if _DECISION_CORE_SINGLETON is not None and _DECISION_CORE_SINGLETON is not core:\n"
        "        raise SystemExit('ARCH_VIOLATION: MULTI_DECISIONCORE')\n"
        "    _DECISION_CORE_SINGLETON = core\n"
    )
    assert _scan_repo_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="core/ai/__init__.py",
        source=safe,
    ) == []

    wrong_path = _scan_repo_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="runtime/private_singleton.py",
        source=safe,
    )
    assert [item.check_id for item in wrong_path] == ["P0_DECISION_AUTHORITY_ALIAS"]

    unguarded = _scan_repo_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="core/ai/__init__.py",
        source=(
            "_DECISION_CORE_SINGLETON = None\n"
            "def set_decision_core_singleton(core):\n"
            "    global _DECISION_CORE_SINGLETON\n"
            "    _DECISION_CORE_SINGLETON = core\n"
        ),
    )
    assert [item.check_id for item in unguarded] == ["P0_DECISION_AUTHORITY_ALIAS"]

    executable = _scan_repo_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="core/ai/__init__.py",
        source="_DECISION_CORE_SINGLETON = RuntimeDecisionCore()\n",
    )
    assert [item.check_id for item in executable] == ["P0_DECISION_AUTHORITY_ALIAS"]


def test_formal_fixture_marker_is_exact_file_shape_and_export_bound(
    tmp_path: Path,
    monkeypatch,
) -> None:
    outside = _scan_repo_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="formal/regression_gate/other_bundle.py",
        source=(
            "class _RejectingDecisionCore:\n"
            "    CANON_NON_RUNTIME_REGRESSION_FIXTURE = True\n"
            "    def evaluate(self, state):\n"
            "        return state\n"
            "    decide = evaluate\n"
        ),
    )
    assert [item.check_id for item in outside] == ["P0_DECISION_AUTHORITY_DEFINITION"]

    sovereign_method = _scan_repo_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="formal/regression_gate/project_snapshot_bundle.py",
        source=(
            "class _RejectingDecisionCore:\n"
            "    CANON_NON_RUNTIME_REGRESSION_FIXTURE = True\n"
            "    def evaluate(self, state):\n"
            "        return state\n"
            "    def issue(self, state):\n"
            "        return state\n"
            "    decide = evaluate\n"
        ),
    )
    assert [item.check_id for item in sovereign_method] == ["P0_DECISION_AUTHORITY_DEFINITION"]

    exported = _scan_repo_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="formal/regression_gate/project_snapshot_bundle.py",
        source=(
            "class _SelectingDecisionCore:\n"
            "    CANON_NON_RUNTIME_REGRESSION_FIXTURE = True\n"
            "    def evaluate(self, state):\n"
            "        return state\n"
            "    decide = evaluate\n"
            "__all__ = ['_SelectingDecisionCore']\n"
        ),
    )
    assert [item.check_id for item in exported] == ["P0_DECISION_AUTHORITY_DEFINITION"]


def test_current_non_authoritative_surfaces_remain_regression_locked() -> None:
    paths = (
        "bootstrap/runtime_dependency_sets.py",
        "canon/collapse/synonym_entity_registry.py",
        "core/ai/__init__.py",
        "core/decision_core.py",
        "formal/regression_gate/project_snapshot_bundle.py",
        "runtime/application/contracts.py",
    )

    residual: dict[str, list[auditor.Finding]] = {}
    for path in paths:
        findings = _scan(Path(path))
        if findings:
            residual[path] = findings

    assert residual == {}


def test_existing_runtime_decision_core_tripwire_stays_fail_closed() -> None:
    path = Path("boot/runtime_service_contracts.py")

    findings = _scan(path)

    assert not [item for item in findings if "RuntimeDecisionCore" in item.message]


def test_canonical_integrity_auditor_keeps_single_owner_contract() -> None:
    assert callable(auditor.run_audit)
    assert callable(auditor.write_reports)
