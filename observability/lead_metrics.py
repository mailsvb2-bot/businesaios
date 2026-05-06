from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from observability import LeadMetrics as LeadMetrics

__all__ = ['LeadMetrics']
