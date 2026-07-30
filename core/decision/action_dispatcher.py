"""Compatibility re-export for the single envelope-only action dispatcher."""

from __future__ import annotations

from application.decision.action_dispatcher import (
    ActionDispatcher,
    DecisionEnvelopeRequiredError,
)

CANON_COMPAT_SHIM = True
CANON_CORE_DECISION_ACTION_DISPATCHER_COMPAT = True
CANONICAL_OWNER_MODULE = "application.decision.action_dispatcher"

__all__ = [
    "ActionDispatcher",
    "CANON_COMPAT_SHIM",
    "CANON_CORE_DECISION_ACTION_DISPATCHER_COMPAT",
    "CANONICAL_OWNER_MODULE",
    "DecisionEnvelopeRequiredError",
]
