from __future__ import annotations

import importlib

from application.decision.action_errors import (
    ActionExecutionRejectedError,
    DecisionApplicationError,
    InvalidActionError,
)
from application.decision.action_result import ActionExecutionResult
from runtime.application import (
    ActionExecutionRejectedError as PublicActionExecutionRejectedError,
)
from runtime.application.action_errors import (
    ActionExecutionRejectedError as CompatActionExecutionRejectedError,
)
from runtime.application.action_result import ActionExecutionResult as CompatActionExecutionResult


def test_runtime_action_result_is_core_owned() -> None:
    result = CompatActionExecutionResult(status="ok", action_type="ping", details={"x": 1})
    assert isinstance(result, ActionExecutionResult)
    assert result.details == {"x": 1}


def test_runtime_action_errors_are_core_owned() -> None:
    assert CompatActionExecutionRejectedError is ActionExecutionRejectedError
    assert issubclass(InvalidActionError, DecisionApplicationError)
    assert PublicActionExecutionRejectedError is ActionExecutionRejectedError


def test_runtime_application_result_error_modules_resolve_via_package_aliases() -> None:
    assert importlib.import_module("runtime.application.action_result") is importlib.import_module(
        "application.decision.action_result"
    )
    assert importlib.import_module("runtime.application.action_errors") is importlib.import_module(
        "application.decision.action_errors"
    )
