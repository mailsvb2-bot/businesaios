"""Explicit compatibility wrapper with a real module file."""

from __future__ import annotations

from config import NotificationDefaults as NotificationDefaults

CANON_COMPAT_SHIM = True

__all__ = ['NotificationDefaults']
