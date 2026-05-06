from pathlib import Path


def test_application_service_uses_port_not_registry() -> None:
    runtime_text = Path("runtime/application/__init__.py").read_text(encoding="utf-8")
    core_text = Path("core/decision/application_service.py").read_text(encoding="utf-8")

    assert '"application_service": "application.decision.decision_service"' in runtime_text
    assert "registry" not in core_text
    assert "RuntimeRegistry" not in core_text
    assert "ReadOnlyRuntimeRegistry" not in core_text
