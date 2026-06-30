"""Compat shim: execution.* forwards to application.recovery.*."""

from __future__ import annotations

from application.recovery.economic_recovery_handoff import *  # noqa: F401,F403

CANON_RECOVERY_COMPAT_SURFACE = True

