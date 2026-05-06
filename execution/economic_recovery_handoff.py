from __future__ import annotations

"""Compat shim: execution.* forwards to application.recovery.*."""

CANON_RECOVERY_COMPAT_SURFACE = True

from application.recovery.economic_recovery_handoff import *  # noqa: F401,F403
