"""Explicit compatibility wrapper with a real module file."""

from __future__ import annotations

from config import RiskThresholds as RiskThresholds

CANON_COMPAT_SHIM = True

__all__ = ['RiskThresholds']
