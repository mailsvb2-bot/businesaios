from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from config import HIGH_VALUE_PRIORITY_WEIGHT as HIGH_VALUE_PRIORITY_WEIGHT
from config import PREMIUM_QUALITY_WEIGHT as PREMIUM_QUALITY_WEIGHT

__all__ = ['HIGH_VALUE_PRIORITY_WEIGHT', 'PREMIUM_QUALITY_WEIGHT']
