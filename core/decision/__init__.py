from __future__ import annotations

"""Canonical core decision namespace.

The package root is a thin compatibility facade. The canonical owner surface is
``application.decision`` and symbol resolution is delegated lazily so importing
submodules such as ``core.decision.ai_decision_trace`` does not create a package
initialization cycle.
"""

from importlib import import_module
from typing import Any
import sys

from canon.public_api_alias import install_public_api_alias

CANON_TRANSITION_SURFACE = True
CANON_CORE_DECISION_NAMESPACE = True
CANON_CORE_DECISION_PACKAGE_OWNER = True
CANON_CORE_DECISION_PUBLIC_API = True
CANON_COMPAT_PUBLIC_API_SHIM = True
CANONICAL_OWNER_DECISION_SURFACE = "application.decision"
CANONICAL_OWNER_PUBLIC_API = "core.decision"

# Historical ownership marker for arch tests:
# from application.decision import (
#     AIDecisionTrace,
#     ActionDispatcher,
#     ActionExecutionRejectedError,
#     ActionExecutionResult,
#     ActionValidator,
#     DecisionApplicationError,
#     DecisionApplicationService,
#     DecisionExecutionPortProtocol,
#     InvalidActionError,
#     ObservabilityPortProtocol,
#     RuntimeDecisionTrace,
#     TraceBuilder,
#     TraceStep,
#     present_action_execution_result,
# )

_EXPORTS = [
    "AIDecisionTrace",
    "ActionDispatcher",
    "ActionExecutionRejectedError",
    "ActionExecutionResult",
    "ActionValidator",
    "CANON_CORE_DECISION_NAMESPACE",
    "CANON_CORE_DECISION_PACKAGE_OWNER",
    "CANON_CORE_DECISION_PUBLIC_API",
    "CANON_COMPAT_PUBLIC_API_SHIM",
    "CANONICAL_OWNER_DECISION_SURFACE",
    "CANONICAL_OWNER_PUBLIC_API",
    "DecisionApplicationError",
    "DecisionApplicationService",
    "DecisionExecutionPortProtocol",
    "InvalidActionError",
    "ObservabilityPortProtocol",
    "RuntimeDecisionTrace",
    "TraceBuilder",
    "TraceStep",
    "present_action_execution_result",
]


def _owner() -> Any:
    return import_module("application.decision")


def __getattr__(name: str) -> Any:
    if name in {
        "CANON_CORE_DECISION_NAMESPACE",
        "CANON_CORE_DECISION_PACKAGE_OWNER",
        "CANON_CORE_DECISION_PUBLIC_API",
        "CANON_COMPAT_PUBLIC_API_SHIM",
        "CANONICAL_OWNER_DECISION_SURFACE",
        "CANONICAL_OWNER_PUBLIC_API",
    }:
        return globals()[name]
    if name in _EXPORTS:
        return getattr(_owner(), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS) | set(dir(_owner())))


__all__ = list(_EXPORTS)


_COMPAT_ALIAS_MAP = {
    "decision_candidate": "core.contracts.decision_candidate",
    "decision_context": "core.contracts.decision_context",
    "decision_reason": "core.contracts.decision_reason",
    "decision_rejection": "core.contracts.decision_rejection",
    "decision_request": "core.contracts.decision_request",
    "decision_result": "core.contracts.decision_result",
    "decision_space": "core.contracts.decision_space",
    "decision_trace": "core.contracts.decision_trace",
    "decision_history": "core.policy.decision_history",
    "decision_publisher": "core.policy.decision_publisher",
    "decision_space_narrowing_audit": "core.policy.decision_space_narrowing_audit",
    "decision_validator": "core.policy.decision_validator",
}


def _install_decision_compat_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target_module_name in _COMPAT_ALIAS_MAP.items():
        target_module = import_module(target_module_name)
        qualified_name = f"{__name__}.{alias_name}"
        sys.modules[qualified_name] = target_module
        setattr(package, alias_name, target_module)

_install_decision_compat_aliases()
install_public_api_alias(__name__)
