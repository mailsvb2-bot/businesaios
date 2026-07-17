from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.application.decision_transition_lock import (
    execute_locked_application_action,
    validate_no_raw_decision_helpers,
)


def build_decision_execution_port(
    *,
    decision_core: object,
) -> DecisionExecutionPort:
    """Build the historical port around an execution-only owner.

    ``decision_core`` is retained as a keyword for compatibility. The supplied
    object must not issue or optimize decisions and must expose only
    ``execute(envelope)``.
    """

    return DecisionExecutionPort(decision_core=decision_core)


def build_observability_port(*, observability: object) -> ObservabilityPort:
    return ObservabilityPort(observability=observability)


def build_nullable_observability_port(
    *,
    observability: object | None,
) -> ObservabilityPort:
    return ObservabilityPort(
        observability=observability or _NullObservability()
    )


class _NullAuditLog:
    def event_names(self) -> tuple[str, ...]:
        return ()


class _NullObservability:
    audit_log = _NullAuditLog()


@dataclass(frozen=True)
class DecisionExecutionPort:
    """Envelope-only runtime execution port.

    The historical field name remains ABI-compatible, but the object is an
    execution owner, never the sovereign DecisionCore.
    """

    decision_core: object

    def __post_init__(self) -> None:
        validate_no_raw_decision_helpers(self.decision_core)
        execute = getattr(self.decision_core, "execute", None)
        if not callable(execute):
            raise TypeError(
                "decision execution owner requires execute(envelope)"
            )

    @property
    def execution_owner(self) -> object:
        return self.decision_core

    def execute(self, envelope: object) -> Any:
        return execute_locked_application_action(
            owner=self.execution_owner,
            action=envelope,
        )

    def execute_action(self, envelope: object) -> Any:
        """Historical method name with envelope-only semantics."""

        return self.execute(envelope)


@dataclass(frozen=True)
class ObservabilityPort:
    """Thin runtime-owned observability port."""

    observability: object

    def audit_events(self) -> tuple[str, ...]:
        audit_log = getattr(self.observability, "audit_log", None)
        event_names = getattr(audit_log, "event_names", None)
        if not callable(event_names):
            raise AttributeError(
                "observability_missing_audit_log_event_names"
            )
        return tuple(event_names())


__all__ = [
    "DecisionExecutionPort",
    "ObservabilityPort",
    "build_decision_execution_port",
    "build_observability_port",
    "build_nullable_observability_port",
]
