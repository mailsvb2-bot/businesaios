"""Compat shim: execution.* forwards to application.evidence.*."""

from __future__ import annotations

from application.evidence.effect_evidence import *  # noqa: F401,F403

CANON_EFFECT_EVIDENCE = True

