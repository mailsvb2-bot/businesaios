"""Explicit compatibility wrapper with a real module file."""

from __future__ import annotations

from config import BudgetLimits as BudgetLimits

CANON_COMPAT_SHIM = True

__all__ = ['BudgetLimits']

