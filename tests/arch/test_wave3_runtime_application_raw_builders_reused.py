from pathlib import Path


def test_runtime_application_contracts_expose_shared_raw_builders() -> None:
    text = Path("runtime/application/contracts.py").read_text(encoding="utf-8")
    assert "def build_runtime_service_exports_from_raw(" in text
    assert "build_nullable_observability_port" in text
    assert "build_decision_execution_port" in text


def test_runtime_ceo_public_api_reuses_shared_raw_builders() -> None:
    text = Path("runtime/ceo/__init__.py").read_text(encoding="utf-8")
    assert "build_runtime_application_service_from_raw(" in text
    assert "def _build_decision_execution_port" not in text
    assert "def _build_observability_port" not in text
