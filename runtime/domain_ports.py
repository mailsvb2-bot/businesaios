"""Thin external shim for canonical runtime application ports."""

from __future__ import annotations

from runtime.application.contracts import DecisionExecutionPort, ObservabilityPort

CANON_COMPAT_SHIM = True
__all__ = ["CANON_COMPAT_SHIM", "DecisionExecutionPort", "ObservabilityPort"]

