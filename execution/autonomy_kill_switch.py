"""Compat shim: execution.* forwards to application.autonomy.*."""

from __future__ import annotations

from application.autonomy.autonomy_kill_switch import *  # noqa: F401,F403

CANON_AUTONOMY_KILL_SWITCH = True

