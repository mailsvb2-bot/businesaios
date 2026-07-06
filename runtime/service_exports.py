"""Thin external shim for runtime application service exports.

This module intentionally re-exports the canonical owner surface from
``runtime.application.contracts``. No registry logic or business logic belongs
here.
"""

from __future__ import annotations

from runtime.application.contracts import RuntimeServiceExports

CANON_COMPAT_SHIM = True

__all__ = ["CANON_COMPAT_SHIM", "RuntimeServiceExports"]
