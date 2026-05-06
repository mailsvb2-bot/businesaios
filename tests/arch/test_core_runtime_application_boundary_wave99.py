from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_runtime_application_package_root_installs_core_aliases() -> None:
    text = _read("runtime/application/__init__.py")
    assert "_ALIAS_MAP" in text
    assert '"action_dispatcher": "application.decision.action_dispatcher"' in text
    assert '"application_ports": "application.decision.ports"' in text
    assert '"application_service": "application.decision.decision_service"' in text
    assert '"action_result": "application.decision.action_result"' in text
    assert '"action_errors": "application.decision.action_errors"' in text
    assert '"action_result_presenter": "application.decision.action_result_presenter"' in text
    assert '"action_validator": "application.decision.action_validator"' in text
    assert "_install_compat_aliases()" in text
    assert "install_public_api=False" in text


def test_collapsed_runtime_application_shim_files_are_removed() -> None:
    for rel in (
        "runtime/application/action_dispatcher.py",
        "runtime/application/application_ports.py",
        "runtime/application/application_service.py",
        "runtime/application/action_result.py",
        "runtime/application/action_errors.py",
        "runtime/application/action_result_presenter.py",
        "runtime/application/action_validator.py",
    ):
        assert not (ROOT / rel).exists(), rel


def test_core_application_now_owns_runtime_application_surface() -> None:
    dispatcher_text = _read("core/application/action_dispatcher.py")
    service_text = _read("core/application/decision_service.py")
    validator_text = _read("core/application/action_validator.py")
    ports_text = _read("core/application/ports.py")

    assert "class ActionDispatcher" in dispatcher_text
    assert "class DecisionApplicationService" in service_text
    assert "application.decision.action_validator" in validator_text
    assert "Protocol" in ports_text
