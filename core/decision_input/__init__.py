"""Compatibility package surface. Final owner: application.decision_input."""

from __future__ import annotations

from application.decision_input import InputRegistry, build_decision_input_contract

CANON_COMPAT_SHIM = True
CANONICAL_OWNER_MODULE = "application.decision_input"
__all__ = ["build_decision_input_contract", "InputRegistry"]

