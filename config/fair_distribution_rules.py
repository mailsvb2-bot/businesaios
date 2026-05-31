"""Explicit compatibility wrapper with a real module file."""

from __future__ import annotations

from config import FAIR_ROTATION_WEIGHT as FAIR_ROTATION_WEIGHT
from config import NEW_SUPPLY_SUPPORT_BONUS as NEW_SUPPLY_SUPPORT_BONUS

CANON_COMPAT_SHIM = True

__all__ = ['FAIR_ROTATION_WEIGHT', 'NEW_SUPPLY_SUPPORT_BONUS']

