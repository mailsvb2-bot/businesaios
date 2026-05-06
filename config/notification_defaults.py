from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from config import NotificationDefaults as NotificationDefaults

__all__ = ['NotificationDefaults']
