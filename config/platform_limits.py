from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from config import PlatformLimits as PlatformLimits

__all__ = ['PlatformLimits']
