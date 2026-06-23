from __future__ import annotations

"""Canonical headless gateway for issuing decisions on one path."""

from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

from core.strategic_horizon.engine import CANONICAL_DECISION_OPTIMIZE_METHOD
from runtime.decision_path_lock import (
    DecisionPathLockError,
    LockedDecisionPath,
    build_decision_path_lock_spec,
    issue_locked_decision,
    lock_decision_for_executor,
    lock_world_state,
    resolve_decision_issue_callable,
)

CANON_HEADLESS_DECISION_GATEWAY_SINGLE_PATH = True
CANON_HEADLESS_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC = True
CANON_HEADLESS_DECISION_GATEWAY_ISSUE_OWNER = True
CANON_HEADLESS_DECISION_INGRESS_OWNER = True
CANON_HEADLESS_DECISION_GATEWAY_COMPAT_ALIAS = True


class HeadlessDecisionGatewayContractError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class HeadlessDecisionIngress:
    decision_core: Any

    def issue(self, state: Any) -> Any:
        validate_headless_decision_core(self.decision_core)
        issue = getattr(self.decision_core, 'issue', None)
        if callable(issue):
            try:
                locked = issue_locked_decision(decision_core=self.decision_core, state=state)
            except DecisionPathLockError as exc:
                raise HeadlessDecisionGatewayContractError(str(exc)) from exc
            return locked.envelope
        optimize = getattr(self.decision_core, CANONICAL_DECISION_OPTIMIZE_METHOD, None)
        if callable(optimize):
            try:
                locked_state = lock_world_state(state=state)
                build_decision_path_lock_spec().require_transition(
                    current_stage=locked_state.stage,
                    next_stage='decision_core',
                )
                envelope = optimize(locked_state.state)
                lock_decision_for_executor(envelope=envelope)
                locked = LockedDecisionPath(
                    stage='decision_core',
                    state=locked_state.state,
                    envelope=envelope,
                )
            except DecisionPathLockError as exc:
                raise HeadlessDecisionGatewayContractError(str(exc)) from exc
            return locked.envelope
        raise HeadlessDecisionGatewayContractError(
            'decision_core_must_provide_callable_issue_or_optimize'
        )


# Transitional ABI only.
HeadlessDecisionGateway = HeadlessDecisionIngress


def _resolve_optimize_callable(decision_core: Any) -> Callable[[Any], Any]:
    optimize = getattr(decision_core, CANONICAL_DECISION_OPTIMIZE_METHOD, None)
    if callable(optimize):
        return optimize
    raise DecisionPathLockError('decision_core_must_provide_callable_issue_or_optimize')


def resolve_headless_decision_callable(decision_core: Any) -> Callable[[Any], Any]:
    try:
        return resolve_decision_issue_callable(decision_core)
    except DecisionPathLockError as issue_error:
        try:
            return _resolve_optimize_callable(decision_core)
        except DecisionPathLockError as optimize_error:
            raise HeadlessDecisionGatewayContractError(str(optimize_error)) from issue_error


def validate_headless_decision_core(decision_core: Any) -> None:
    resolve_headless_decision_callable(decision_core)


def build_headless_decision_ingress(*, decision_core: Any) -> HeadlessDecisionIngress:
    validate_headless_decision_core(decision_core)
    return HeadlessDecisionIngress(decision_core=decision_core)


def issue_headless_decision(*, decision_core: Any, state: Any) -> Any:
    try:
        return build_headless_decision_ingress(decision_core=decision_core).issue(state)
    except HeadlessDecisionGatewayContractError:
        raise


__all__ = [
    'CANON_HEADLESS_DECISION_GATEWAY_COMPAT_ALIAS',
    'CANON_HEADLESS_DECISION_GATEWAY_ISSUE_OWNER',
    'CANON_HEADLESS_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC',
    'CANON_HEADLESS_DECISION_GATEWAY_SINGLE_PATH',
    'CANON_HEADLESS_DECISION_INGRESS_OWNER',
    'HeadlessDecisionGateway',
    'HeadlessDecisionGatewayContractError',
    'HeadlessDecisionIngress',
    'build_headless_decision_ingress',
    'issue_headless_decision',
    'resolve_headless_decision_callable',
    'validate_headless_decision_core',
]
