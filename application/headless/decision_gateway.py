"""Headless compatibility surface for the canonical runtime decision gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from runtime.decision_gateway import (
    DecisionGatewayContractError,
    build_runtime_decision_callable,
    issue_runtime_decision,
    validate_runtime_decision_issuer,
)

CANON_HEADLESS_DECISION_GATEWAY_SINGLE_PATH = True
CANON_HEADLESS_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC = True
CANON_HEADLESS_DECISION_GATEWAY_ISSUE_OWNER = False
CANON_HEADLESS_DECISION_INGRESS_OWNER = True
CANON_HEADLESS_DECISION_GATEWAY_COMPAT_ALIAS = True
CANON_HEADLESS_DECISION_GATEWAY_DELEGATES_TO_RUNTIME = True


class HeadlessDecisionGatewayContractError(RuntimeError):
    pass


_MISSING_DECISION_ISSUER_MESSAGE = (
    "decision_core must provide callable issue() or optimize()"
)


def _translate_contract_error(exc: Exception) -> HeadlessDecisionGatewayContractError:
    code = str(exc)
    if code in {
        "decision_core_missing",
        "decision_core_must_provide_callable_issue_or_optimize",
    }:
        code = _MISSING_DECISION_ISSUER_MESSAGE
    return HeadlessDecisionGatewayContractError(code)


@dataclass(slots=True, frozen=True)
class HeadlessDecisionIngress:
    decision_core: Any

    def issue(self, state: Any) -> Any:
        try:
            return issue_runtime_decision(
                issuer=self.decision_core,
                state=state,
            )
        except DecisionGatewayContractError as exc:
            raise _translate_contract_error(exc) from exc


HeadlessDecisionGateway = HeadlessDecisionIngress


def resolve_headless_decision_callable(
    decision_core: Any,
) -> Callable[[Any], Any]:
    try:
        return build_runtime_decision_callable(issuer=decision_core)
    except DecisionGatewayContractError as exc:
        raise _translate_contract_error(exc) from exc


def validate_headless_decision_core(decision_core: Any) -> None:
    try:
        validate_runtime_decision_issuer(decision_core)
    except DecisionGatewayContractError as exc:
        raise _translate_contract_error(exc) from exc


def build_headless_decision_ingress(
    *,
    decision_core: Any,
) -> HeadlessDecisionIngress:
    validate_headless_decision_core(decision_core)
    return HeadlessDecisionIngress(decision_core=decision_core)


def issue_headless_decision(*, decision_core: Any, state: Any) -> Any:
    """Delegate the historical headless helper to the sole runtime issuer."""

    try:
        return issue_runtime_decision(
            issuer=decision_core,
            state=state,
        )
    except DecisionGatewayContractError as exc:
        raise _translate_contract_error(exc) from exc


__all__ = [
    "CANON_HEADLESS_DECISION_GATEWAY_COMPAT_ALIAS",
    "CANON_HEADLESS_DECISION_GATEWAY_ISSUE_OWNER",
    "CANON_HEADLESS_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC",
    "CANON_HEADLESS_DECISION_GATEWAY_SINGLE_PATH",
    "CANON_HEADLESS_DECISION_INGRESS_OWNER",
    "CANON_HEADLESS_DECISION_GATEWAY_DELEGATES_TO_RUNTIME",
    "HeadlessDecisionGateway",
    "HeadlessDecisionGatewayContractError",
    "HeadlessDecisionIngress",
    "build_headless_decision_ingress",
    "issue_headless_decision",
    "resolve_headless_decision_callable",
    "validate_headless_decision_core",
]
