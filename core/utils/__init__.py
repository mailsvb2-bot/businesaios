"""Core utility namespace.

Kept intentionally lightweight so canonical helpers can be imported by kernel
signing/crypto modules in clean release checks.
"""
from __future__ import annotations

CANON_CORE_UTILS_NAMESPACE = True

__all__ = ["CANON_CORE_UTILS_NAMESPACE"]
