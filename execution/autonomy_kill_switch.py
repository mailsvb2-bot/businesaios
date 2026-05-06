from __future__ import annotations

"""Compat shim: execution.* forwards to application.autonomy.*."""

CANON_AUTONOMY_KILL_SWITCH = True

from application.autonomy.autonomy_kill_switch import *  # noqa: F401,F403
