"""Single-owner decision path contract.

This module contains only structural validation for the canonical decision path:
    world_state -> explicit DecisionCore issue()/optimize() -> envelope -> executor

It must not become a second decision engine or add pre-decision business logic.
The passed issuer is the complete decision dependency for one invocation; the
runtime path never consults process-global singleton state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

CANON_DECISION_PATH_LOCK_SINGLE_OWNER = True
CANON_DECISION_PATH_LOCK_FAIL_CLOSED = True
CANON_DECISION_PATH_LOCK_NO_DECISION_LOGIC = True
CANON_DECISION_PATH_LOCK_BINDS_REGISTERED_SINGLETON = False
CANON_DECISION_PATH_LOCK_USES_EXPLICIT_ISSUER = True
CANON_DECISION_PATH_LOCK_NO_HIDDEN_GLOBAL_STATE = True
CANON_DECISION_PATH_LOCK_COMPAT_OPTIMIZE_ALIAS = True
CANON_DECISION_PATH_ORDER = (
    "world_state",
    "decision_core",
    "executor",
)


class DecisionPathLockError(RuntimeError):
    pass


DecisionIssuerMethod = Literal["issue", "optimize"]


@dataclass(frozen=True, slots=True)
class DecisionIssuerBinding:
    """Frozen structural binding to exactly one passed decision issuer.

    The binding chooses one compatibility method once, with ``issue`` taking
    precedence over ``optimize``. It contains no ranking or decision logic and
    therefore cannot become a second brain.
    """

    decision_core: Any
    method_name: DecisionIssuerMethod
    invoke: Callable[[Any], Any]


@dataclass(frozen=True)
class LockedDecisionPath:
    stage: str
    state: Any | None = None
    envelope: Any | None = None


@dataclass(frozen=True)
class DecisionPathLockSpec:
    order: tuple[str, ...] = CANON_DECISION_PATH_ORDER

    def index_of(self, stage: str) -> int:
        try:
            return self.order.index(stage)
        except ValueError as exc:
            raise DecisionPathLockError(
                f"unknown_decision_stage:{stage}"
            ) from exc

    def require_transition(
        self,
        *,
        current_stage: str,
        next_stage: str,
    ) -> None:
        current_index = self.index_of(current_stage)
        next_index = self.index_of(next_stage)
        if next_index != current_index + 1:
            raise DecisionPathLockError(
                f"invalid_decision_transition:{current_stage}->{next_stage}"
            )


_DEFAULT_SPEC = DecisionPathLockSpec()


def build_decision_path_lock_spec() -> DecisionPathLockSpec:
    return _DEFAULT_SPEC


def _validate_world_state_shape(state: Any) -> None:
    if state is None:
        raise DecisionPathLockError("decision_world_state_missing")
    if getattr(state, "decision", None) is not None:
        raise DecisionPathLockError(
            "decision_world_state_must_not_be_envelope"
        )
    if (
        getattr(state, "action", None) is not None
        and getattr(state, "payload", None) is not None
    ):
        raise DecisionPathLockError(
            "decision_world_state_must_not_be_action_like"
        )


def _validate_decision_envelope_shape(envelope: Any) -> None:
    decision = getattr(envelope, "decision", None)
    if decision is None:
        raise DecisionPathLockError("decision_envelope_missing_decision")
    if not str(getattr(decision, "decision_id", "") or "").strip():
        raise DecisionPathLockError(
            "decision_envelope_missing_decision_id"
        )
    if not str(
        getattr(decision, "correlation_id", "") or ""
    ).strip():
        raise DecisionPathLockError(
            "decision_envelope_missing_correlation_id"
        )


def lock_world_state(*, state: Any) -> LockedDecisionPath:
    _validate_world_state_shape(state)
    return LockedDecisionPath(stage="world_state", state=state)


def bind_decision_issuer(
    decision_core: Any,
    *,
    method_name: DecisionIssuerMethod | None = None,
) -> DecisionIssuerBinding:
    """Bind the explicitly supplied issuer without consulting global state."""

    if isinstance(decision_core, DecisionIssuerBinding):
        if method_name is None or decision_core.method_name == method_name:
            return decision_core
        decision_core = decision_core.decision_core

    if decision_core is None:
        raise DecisionPathLockError("decision_core_missing")

    method_order: tuple[DecisionIssuerMethod, ...]
    if method_name is None:
        method_order = ("issue", "optimize")
    else:
        method_order = (method_name,)

    for candidate_name in method_order:
        candidate = getattr(decision_core, candidate_name, None)
        if callable(candidate):
            return DecisionIssuerBinding(
                decision_core=decision_core,
                method_name=candidate_name,
                invoke=candidate,
            )

    if method_name is not None:
        raise DecisionPathLockError(
            f"decision_core_must_provide_callable_{method_name}"
        )
    raise DecisionPathLockError(
        "decision_core_must_provide_callable_issue_or_optimize"
    )


def resolve_decision_issue_callable(
    decision_core: Any,
) -> Callable[[Any], Any]:
    """Resolve the one compatibility issuer callable.

    The historical function name is retained for ABI compatibility. It accepts
    the canonical ``issue`` method or the documented ``optimize`` alias.
    """

    return bind_decision_issuer(decision_core).invoke


def issue_locked_decision(
    *,
    decision_core: Any,
    state: Any,
) -> LockedDecisionPath:
    binding = bind_decision_issuer(decision_core)
    locked_state = lock_world_state(state=state)
    build_decision_path_lock_spec().require_transition(
        current_stage=locked_state.stage,
        next_stage="decision_core",
    )
    envelope = binding.invoke(locked_state.state)
    _validate_decision_envelope_shape(envelope)
    return LockedDecisionPath(
        stage="decision_core",
        state=locked_state.state,
        envelope=envelope,
    )


def lock_decision_for_executor(*, envelope: Any) -> LockedDecisionPath:
    _validate_decision_envelope_shape(envelope)
    build_decision_path_lock_spec().require_transition(
        current_stage="decision_core",
        next_stage="executor",
    )
    return LockedDecisionPath(stage="executor", envelope=envelope)


__all__ = [
    "CANON_DECISION_PATH_LOCK_SINGLE_OWNER",
    "CANON_DECISION_PATH_LOCK_FAIL_CLOSED",
    "CANON_DECISION_PATH_LOCK_NO_DECISION_LOGIC",
    "CANON_DECISION_PATH_LOCK_BINDS_REGISTERED_SINGLETON",
    "CANON_DECISION_PATH_LOCK_USES_EXPLICIT_ISSUER",
    "CANON_DECISION_PATH_LOCK_NO_HIDDEN_GLOBAL_STATE",
    "CANON_DECISION_PATH_LOCK_COMPAT_OPTIMIZE_ALIAS",
    "CANON_DECISION_PATH_ORDER",
    "DecisionIssuerBinding",
    "DecisionIssuerMethod",
    "DecisionPathLockError",
    "DecisionPathLockSpec",
    "LockedDecisionPath",
    "bind_decision_issuer",
    "build_decision_path_lock_spec",
    "lock_world_state",
    "resolve_decision_issue_callable",
    "issue_locked_decision",
    "lock_decision_for_executor",
]
