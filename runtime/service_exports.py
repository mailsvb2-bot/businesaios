from __future__ import annotations

from runtime.application.contracts import RuntimeServiceExports

"""Thin external shim for runtime application service exports.

This module intentionally re-exports the canonical owner surface from
``runtime.application.contracts``. No registry logic or business logic belongs
here.
"""

CANON_COMPAT_SHIM = True

__all__ = ["CANON_COMPAT_SHIM", "RuntimeServiceExports"]
