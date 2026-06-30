"""Thin compatibility surface for the canonical runtime executor contract.

This module intentionally re-exports only the explicit public symbols from
``runtime.execution.contracts``. Wildcard exports at the root ``runtime/``
layer make ownership blurry and tend to regrow broad public surfaces.
"""

from __future__ import annotations

from runtime.execution.contracts import (
    RUNTIME_EXECUTOR_CONTRACT_VERSION,
    RuntimeExecutorPort,
)

CANON_RUNTIME_EXECUTOR_CONTRACT_THIN_SHIM = True
CANON_RUNTIME_EXECUTOR_CONTRACT_EXPLICIT_EXPORTS_ONLY = True
CANON_RUNTIME_EXECUTOR_CONTRACT_OWNER = "runtime.execution.contracts"
__all__ = [
    "CANON_RUNTIME_EXECUTOR_CONTRACT_THIN_SHIM",
    "CANON_RUNTIME_EXECUTOR_CONTRACT_EXPLICIT_EXPORTS_ONLY",
    "CANON_RUNTIME_EXECUTOR_CONTRACT_OWNER",
    "RUNTIME_EXECUTOR_CONTRACT_VERSION",
    "RuntimeExecutorPort",
]

