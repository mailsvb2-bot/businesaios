from __future__ import annotations

"""Compat shim: execution.* forwards to application.capability.*."""

CANON_CAPABILITY_COMPAT_SURFACE = True
# compatibility owner: application.capability.action_capability_matrix

from application.capability.action_capability_matrix import *  # noqa: F401,F403
