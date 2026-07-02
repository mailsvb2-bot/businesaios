from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "boot" / "runtime_service_contracts.py"
REGISTRATION = ROOT / "boot" / "registrations" / "register_decision_core.py"


def test_runtime_decision_core_executable_alias_is_not_restored() -> None:
    text = CONTRACTS.read_text(encoding="utf-8")
    forbidden_alias = "RuntimeDecisionCore" + " = " + "RuntimeDecisionExecutionService"

    assert forbidden_alias not in text
    assert "class RuntimeDecisionCore" in text
    assert "CANON_RUNTIME_DECISION_CORE_COMPAT_TRIPWIRE" in text


def test_runtime_registration_does_not_export_runtime_decision_core() -> None:
    text = REGISTRATION.read_text(encoding="utf-8")

    assert "RuntimeDecisionCore" not in text
    assert "RuntimeDecisionExecutionService" in text
    assert "CANON_REGISTER_DECISION_CORE_NO_EXECUTABLE_ALIAS_EXPORT" in text
