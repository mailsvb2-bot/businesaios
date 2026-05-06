from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_application_contracts_expose_single_path_builder() -> None:
    text = (ROOT / "runtime" / "application" / "contracts.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_APPLICATION_SINGLE_DECISION_PATH = True" in text
    assert "def build_runtime_application_service(" in text
    assert "def build_runtime_application_service_from_exports(" in text
    assert "DecisionApplicationService(" in text


def test_runtime_integration_delegates_application_service_to_runtime_application_contracts() -> None:
    text = (ROOT / "boot" / "runtime_integration.py").read_text(encoding="utf-8")
    assert "build_runtime_application_service" in text
    assert "ReadOnlyRuntimeRegistry" in text
    assert "DecisionApplicationService(" not in text
