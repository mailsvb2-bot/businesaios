from __future__ import annotations

"""Compat shim: execution.* forwards to application.capability.*."""

CANON_CAPABILITY_COMPAT_SURFACE = True
# compatibility owner: application.capability.capability_health_policy

from application.capability.capability_health_policy import *  # noqa: F401,F403
