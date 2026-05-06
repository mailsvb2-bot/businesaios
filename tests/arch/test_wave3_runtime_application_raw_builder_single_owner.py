from pathlib import Path


def test_runtime_ceo_public_api_uses_raw_application_builder_owner() -> None:
    text = Path("runtime/ceo/__init__.py").read_text(encoding="utf-8")
    assert "build_runtime_application_service_from_raw(" in text
    assert "_ExportsBackedRegistry" not in text
    assert "build_runtime_application_service(" not in text


def test_runtime_application_contracts_expose_raw_application_builder() -> None:
    text = Path("runtime/application/contracts.py").read_text(encoding="utf-8")
    assert "def build_runtime_application_service_from_raw(" in text
    assert "build_runtime_service_exports_from_raw(" in text
