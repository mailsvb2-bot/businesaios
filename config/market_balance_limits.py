from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from config import MAX_CONCENTRATION_RATIO as MAX_CONCENTRATION_RATIO
from config import UTILIZATION_WARN_RATIO as UTILIZATION_WARN_RATIO
from config import OVERFLOW_WARN_RATIO as OVERFLOW_WARN_RATIO

__all__ = ['MAX_CONCENTRATION_RATIO', 'UTILIZATION_WARN_RATIO', 'OVERFLOW_WARN_RATIO']
