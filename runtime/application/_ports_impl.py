from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.application.decision_transition_lock import (
    execute_locked_application_action,
    resolve_transition_execute_callable,
    validate_no_raw_decision_helpers,
)


def build_decision_execution_port(*, decision_core: object) -> "DecisionExecutionPort":
    return DecisionExecutionPort(decision_core=decision_core)


def build_observability_port(*, observability: object) -> "ObservabilityPort":
    return ObservabilityPort(observability=observability)


def build_nullable_observability_port(*, observability: object | None) -> "ObservabilityPort":
    return ObservabilityPort(observability=observability or _NullObservability())


class _NullAuditLog:
    def event_names(self) -> tuple[str, ...]:
        return ()


class _NullObservability:
    audit_log = _NullAuditLog()


@dataclass(frozen=True)
class DecisionExecutionPort:
    """Thin runtime-owned execution port.

    This surface is intentionally tiny: it exposes only the canonical action
    execution contract backed by the single runtime decision/execution owner.
    No registry access or alternate decision path lives here.
    """

    decision_core: object

    def __getattr__(self, name: str):
        if name != "decide_and_execute":
            raise AttributeError(name)
        validate_no_raw_decision_helpers(self)
        try:
            return resolve_transition_execute_callable(self.decision_core).call
        except Exception as exc:
            raise AttributeError("decision_core_missing_decide_and_execute") from exc

    def execute_action(self, action: object) -> dict[str, Any]:
        return execute_locked_application_action(owner=self.decision_core, action=action)


@dataclass(frozen=True)
class ObservabilityPort:
    """Thin runtime-owned observability port."""

    observability: object

    def audit_events(self) -> tuple[str, ...]:
        audit_log = getattr(self.observability, "audit_log", None)
        event_names = getattr(audit_log, "event_names", None)
        if not callable(event_names):
            raise AttributeError("observability_missing_audit_log_event_names")
        return tuple(event_names())


__all__ = [
    "DecisionExecutionPort",
    "ObservabilityPort",
    "build_decision_execution_port",
    "build_observability_port",
    "build_nullable_observability_port",
]
