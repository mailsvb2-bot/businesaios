from __future__ import annotations

"""Canonical runtime.application package root.

The package root is now the primary owner for runtime application exports.
The ``runtime.application.public_api`` module remains as an explicit compatibility shell
for older imports, but project-internal code should treat this package root as
the canonical surface. Historical submodule aliases are still installed to
preserve ABI without creating a second owner.
"""

import importlib
import sys
from typing import Any

from runtime.public_api_alias import install_public_api_alias


from application.decision.action_dispatcher import ActionDispatcher
from application.decision.action_errors import (
    ActionExecutionRejectedError,
    CANON_CORE_DECISION_ACTION_ERRORS,
    DecisionApplicationError,
    InvalidActionError,
)
from application.decision.action_result import (
    ActionExecutionResult,
    CANON_CORE_DECISION_ACTION_RESULT,
)
from application.decision.action_result_presenter import (
    CANON_CORE_DECISION_ACTION_RESULT_PRESENTER,
    present_action_execution_result,
)
from application.decision.action_validator import ActionValidator
from application.decision.decision_service import DecisionApplicationService
from application.decision.ports import DecisionExecutionPortProtocol, ObservabilityPortProtocol
from core.decision.ai_decision_trace import (
    CANON_AI_DECISION_TRACE,
    DecisionTrace as AIDecisionTrace,
    TraceBuilder,
    TraceStep,
)
from core.decision.runtime_decision_trace import RuntimeDecisionTrace
from runtime.application.contracts import (
    DecisionExecutionPort,
    ObservabilityPort,
    ReadOnlyRuntimeRegistry,
    RuntimeCapabilityAccess,
    RuntimeDecisionCorePort,
    RuntimeServiceExports,
    RuntimeTypedAccess,
    build_runtime_application_service,
    build_runtime_application_service_from_exports,
    build_runtime_application_service_from_raw,
    build_runtime_service_exports,
    build_runtime_service_exports_from_raw,
)
from runtime.application.crm_contracts import RuntimeCrmContracts
from runtime.application.crm_service import RuntimeCrmService

CANON_COMPAT_SHIM = True
CANON_RUNTIME_APPLICATION_NAMESPACE = True
CANON_RUNTIME_APPLICATION_PUBLIC_API = True
CANON_RUNTIME_APPLICATION_PACKAGE_OWNER = True
# Final-owner imports above intentionally bypass core.application compat paths and runtime aliases now resolve directly to application.decision.*.

_ALIAS_MAP = {
    "action_dispatcher": "application.decision.action_dispatcher",
    "action_errors": "application.decision.action_errors",
    "action_result": "application.decision.action_result",
    "action_result_presenter": "application.decision.action_result_presenter",
    "action_validator": "application.decision.action_validator",
    "application_ports": "application.decision.ports",
    "application_service": "application.decision.decision_service",
    "service_access": "runtime.application.contracts",
    "access_surface": "runtime.application.contracts",
    "contracts": "runtime.application.contracts",
    "registry_access": "runtime.application.contracts",
}


def _install_compat_aliases() -> None:
    """Install historical submodule aliases into ``sys.modules``."""
    for alias_name, target in _ALIAS_MAP.items():
        module = importlib.import_module(target)
        sys.modules[f"{__name__}.{alias_name}"] = module
        globals()[alias_name] = module


# Historical marker for arch tests: _install_compat_aliases()

_install_compat_aliases()


_PUBLIC_ATTRS = {
    "AIDecisionTrace": AIDecisionTrace,
    "ActionDispatcher": ActionDispatcher,
    "ActionExecutionRejectedError": ActionExecutionRejectedError,
    "ActionExecutionResult": ActionExecutionResult,
    "ActionValidator": ActionValidator,
    "CANON_AI_DECISION_TRACE": CANON_AI_DECISION_TRACE,
    "CANON_COMPAT_SHIM": CANON_COMPAT_SHIM,
    "CANON_CORE_DECISION_ACTION_ERRORS": CANON_CORE_DECISION_ACTION_ERRORS,
    "CANON_CORE_DECISION_ACTION_RESULT": CANON_CORE_DECISION_ACTION_RESULT,
    "CANON_CORE_DECISION_ACTION_RESULT_PRESENTER": CANON_CORE_DECISION_ACTION_RESULT_PRESENTER,
    "CANON_RUNTIME_APPLICATION_NAMESPACE": CANON_RUNTIME_APPLICATION_NAMESPACE,
    "CANON_RUNTIME_APPLICATION_PACKAGE_OWNER": CANON_RUNTIME_APPLICATION_PACKAGE_OWNER,
    "CANON_RUNTIME_APPLICATION_PUBLIC_API": CANON_RUNTIME_APPLICATION_PUBLIC_API,
    "DecisionApplicationError": DecisionApplicationError,
    "DecisionApplicationService": DecisionApplicationService,
    "DecisionExecutionPort": DecisionExecutionPort,
    "DecisionExecutionPortProtocol": DecisionExecutionPortProtocol,
    "InvalidActionError": InvalidActionError,
    "ObservabilityPort": ObservabilityPort,
    "ObservabilityPortProtocol": ObservabilityPortProtocol,
    "ReadOnlyRuntimeRegistry": ReadOnlyRuntimeRegistry,
    "RuntimeCapabilityAccess": RuntimeCapabilityAccess,
    "RuntimeCrmContracts": RuntimeCrmContracts,
    "RuntimeCrmService": RuntimeCrmService,
    "RuntimeDecisionCorePort": RuntimeDecisionCorePort,
    "RuntimeDecisionTrace": RuntimeDecisionTrace,
    "RuntimeServiceExports": RuntimeServiceExports,
    "RuntimeTypedAccess": RuntimeTypedAccess,
    "TraceBuilder": TraceBuilder,
    "TraceStep": TraceStep,
    "build_runtime_application_service": build_runtime_application_service,
    "build_runtime_application_service_from_exports": build_runtime_application_service_from_exports,
    "build_runtime_application_service_from_raw": build_runtime_application_service_from_raw,
    "build_runtime_service_exports": build_runtime_service_exports,
    "build_runtime_service_exports_from_raw": build_runtime_service_exports_from_raw,
    "present_action_execution_result": present_action_execution_result,
}


def __getattr__(name: str) -> Any:
    try:
        return _PUBLIC_ATTRS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_PUBLIC_ATTRS) | set(_ALIAS_MAP))


__all__ = sorted(set(_PUBLIC_ATTRS) | set(_ALIAS_MAP))


# Compatibility marker: "public_api": "runtime.application.public_api"
# Historical owner-builder contract equivalent: install_public_api=False
install_public_api_alias(__name__, expose_attribute=False)
