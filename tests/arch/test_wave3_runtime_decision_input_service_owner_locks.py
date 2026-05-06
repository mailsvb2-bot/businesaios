from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_runtime_decision_input_service_declares_single_owner_builder() -> None:
    text = _text("runtime/decision_input/decision_input_service.py")
    assert "CANON_RUNTIME_DECISION_INPUT_SERVICE_OWNER = True" in text
    assert "def build_decision_input_service(" in text


def test_runtime_state_enrichment_service_declares_single_owner_builder() -> None:
    text = _text("runtime/decision_input/runtime_state_enrichment.py")
    assert "CANON_RUNTIME_STATE_ENRICHMENT_SERVICE_OWNER = True" in text
    assert "def build_runtime_state_enrichment_service(" in text


def test_runtime_decision_gateway_declares_single_owner_builder() -> None:
    text = _text("runtime/decision_gateway.py")
    assert "def build_runtime_decision_gateway(" in text


def test_boot_factory_catalog_delegates_to_runtime_service_builders() -> None:
    text = _text("boot/factories/catalog.py")
    assert "build_runtime_decision_gateway(" in text
    assert "build_runtime_decision_input_service(" in text
    assert "build_runtime_state_enrichment_service(" in text
    assert "DecisionGateway(" not in text
    assert "DecisionInputService(observability=" not in text
    assert "RuntimeStateEnrichmentService(observability=" not in text
