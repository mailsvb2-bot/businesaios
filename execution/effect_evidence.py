from __future__ import annotations

"""Compat shim: execution.* forwards to application.evidence.*."""

CANON_EFFECT_EVIDENCE = True

from application.evidence.effect_evidence import *  # noqa: F401,F403
