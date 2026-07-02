from __future__ import annotations

import pytest

from boot.registrations import register_decision_core as registration
from boot.runtime_service_contracts import RuntimeDecisionCore, RuntimeDecisionExecutionService


def test_runtime_decision_core_is_not_alias_to_execution_service() -> None:
    assert RuntimeDecisionCore is not RuntimeDecisionExecutionService
    assert getattr(RuntimeDecisionCore, "CANON_RUNTIME_DECISION_CORE_COMPAT_TRIPWIRE", False) is True


def test_runtime_decision_core_tripwire_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="compatibility alias is removed"):
        RuntimeDecisionCore()


def test_registration_surface_exports_only_runtime_execution_service() -> None:
    assert "RuntimeDecisionExecutionService" in registration.__all__
    assert "RuntimeDecisionCore" not in registration.__all__
    assert registration.CANON_REGISTER_DECISION_CORE_NO_EXECUTABLE_ALIAS_EXPORT is True
