from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from observability import RevenueMetrics as RevenueMetrics

__all__ = ['RevenueMetrics']
