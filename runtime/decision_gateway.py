"""Public adapter for the single canonical runtime decision gateway owner."""

from __future__ import annotations

from runtime.decision_gateway_owner import (
    COMPAT_DECISION_GATEWAY_FUNCTION,
    CANON_RUNTIME_DECISION_GATEWAY_BINDS_REGISTERED_SINGLETON,
    CANON_RUNTIME_DECISION_GATEWAY_COMPAT_ALIAS,
    CANON_RUNTIME_DECISION_GATEWAY_NAME_RESERVED_FOR_ROUTE_OWNER,
    CANON_RUNTIME_DECISION_GATEWAY_NO_HIDDEN_GLOBAL_STATE,
    CANON_RUNTIME_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC,
    CANON_RUNTIME_DECISION_GATEWAY_NO_STRUCTURED_ALT_ISSUER,
    CANON_RUNTIME_DECISION_GATEWAY_OWNS_EXECUTION_SEQUENCE,
    CANON_RUNTIME_DECISION_GATEWAY_REJECTS_SYNTHETIC_ENVELOPES,
    CANON_RUNTIME_DECISION_GATEWAY_SINGLE_PATH,
    CANON_RUNTIME_DECISION_GATEWAY_USES_EXPLICIT_ISSUER,
    CANON_RUNTIME_DECISION_ROUTE_GATEWAY_OWNER,
    DecisionGateway,
    DecisionGatewayContractError,
    DecisionIssuer,
    RuntimeDecisionGateway,
    RuntimeDecisionIssueGateway,
    RuntimeDecisionRouteGateway,
    build_runtime_decision_callable,
    build_runtime_decision_gateway,
    execute_runtime_decision,
    issue_runtime_decision,
    optimize_runtime_decision,
    route_and_issue_runtime_decision,
    validate_runtime_decision_issuer,
    _registered_decision_core,
)

CANON_RUNTIME_DECISION_GATEWAY_PUBLIC_ADAPTER = True

__all__ = [name for name in globals() if not name.startswith("_")]
