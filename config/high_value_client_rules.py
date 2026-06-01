"""Explicit compatibility wrapper with a real module file."""

from __future__ import annotations

from config import HIGH_VALUE_PRIORITY_WEIGHT as HIGH_VALUE_PRIORITY_WEIGHT
from config import PREMIUM_QUALITY_WEIGHT as PREMIUM_QUALITY_WEIGHT

CANON_COMPAT_SHIM = True

__all__ = ['HIGH_VALUE_PRIORITY_WEIGHT', 'PREMIUM_QUALITY_WEIGHT']
