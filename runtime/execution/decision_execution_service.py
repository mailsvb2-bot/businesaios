from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Protocol

from runtime.execution.contracts import RuntimeExecutorPort
from runtime.execution.execution_path_lock import (
    execute_locked_decision,
    validate_and_lock_execution_path,
)


CANON_RUNTIME_DECISION_EXECUTION_SERVICE_OWNER = True
CANON_RUNTIME_DECISION_EXECUTION_RUN_OWNER = True
CANON_RUNTIME_DECISION_EXECUTION_BOUND_SERVICE_OWNER = True


class KeyringLike(Protocol):
    ...


@dataclass(frozen=True)
class BoundDecisionExecutionServiceSpec:
    executor: RuntimeExecutorPort
    keyring: KeyringLike


def build_decision_execution_service(
    executor: RuntimeExecutorPort,
    *,
    keyring: Any | None = None,
) -> "DecisionExecutionService":
    return DecisionExecutionService(executor=executor, keyring=keyring)


def build_bound_decision_execution_service(
    *,
    executor: RuntimeExecutorPort,
    keyring: KeyringLike,
) -> "DecisionExecutionService":
    return build_decision_execution_service(executor=executor, keyring=keyring)


def build_bound_decision_execution_service_spec(
    *,
    executor: RuntimeExecutorPort,
    keyring: KeyringLike,
) -> BoundDecisionExecutionServiceSpec:
    return BoundDecisionExecutionServiceSpec(executor=executor, keyring=keyring)


def validate_and_run_decision_command(
    *,
    service: "DecisionExecutionService",
    command: Any,
) -> Any:
    return service.run(command)


class DecisionExecutionService:
    def __init__(self, executor: RuntimeExecutorPort, *, keyring: Any | None = None) -> None:
        self._executor = executor
        self._keyring = keyring

    def bind_keyring(self, keyring: Any) -> "DecisionExecutionService":
        self._keyring = keyring
        return self

    def run(self, command: Any) -> Any:
        if self._keyring is None:
            raise RuntimeError(
                "DecisionExecutionService requires keyring to sign DecisionCommand envelopes"
            )
        locked_path = validate_and_lock_execution_path(command=command, keyring=self._keyring)
        return execute_locked_decision(executor=self._executor, locked_path=locked_path)


__all__ = [
    "BoundDecisionExecutionServiceSpec",
    "CANON_RUNTIME_DECISION_EXECUTION_BOUND_SERVICE_OWNER",
    "CANON_RUNTIME_DECISION_EXECUTION_RUN_OWNER",
    "CANON_RUNTIME_DECISION_EXECUTION_SERVICE_OWNER",
    "DecisionExecutionService",
    "build_bound_decision_execution_service",
    "build_bound_decision_execution_service_spec",
    "build_decision_execution_service",
    "importlib",
    "validate_and_run_decision_command",
]
