from __future__ import annotations

import importlib

from application.decision.action_result import ActionExecutionResult
from application.decision.action_result_presenter import present_action_execution_result
from runtime.application import (
    present_action_execution_result as public_present_action_execution_result,
)
from runtime.application.action_result_presenter import (
    present_action_execution_result as compat_present_action_execution_result,
)


def test_runtime_action_result_presenter_is_core_owned() -> None:
    raw = {"status": "ok", "action_type": "ping", "reason": "done", "x": 1}

    result = compat_present_action_execution_result(raw)

    assert isinstance(result, ActionExecutionResult)
    assert result.status == "ok"
    assert result.action_type == "ping"
    assert result.reason == "done"
    assert result.details == raw


def test_public_api_reexports_canonical_action_result_presenter() -> None:
    assert public_present_action_execution_result is present_action_execution_result


def test_runtime_application_presenter_module_resolves_via_package_alias() -> None:
    assert importlib.import_module("runtime.application.action_result_presenter") is importlib.import_module(
        "application.decision.action_result_presenter"
    )
