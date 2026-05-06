from __future__ import annotations

"""Compat shim: execution.* forwards to application.autonomy.*."""

CANON_AUTONOMY_POLICY = True

from application.autonomy.autonomy_policy import *  # noqa: F401,F403
