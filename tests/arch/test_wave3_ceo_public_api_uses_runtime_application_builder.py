from pathlib import Path


def test_runtime_ceo_public_api_uses_runtime_application_builder() -> None:
    text = Path("runtime/ceo/__init__.py").read_text(encoding="utf-8")
    assert "build_runtime_application_service_from_raw(" in text
    assert "build_runtime_application_service(" not in text
    assert "DecisionApplicationService(" not in text
    assert "_ExportsBackedRegistry" not in text
