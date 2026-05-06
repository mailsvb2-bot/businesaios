from __future__ import annotations

"""Compat shim: execution.* forwards to application.autonomy.*."""

CANON_AUTONOMY_LOOP = True

from application.autonomy.autonomy_loop import *  # noqa: F401,F403
