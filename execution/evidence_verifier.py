from __future__ import annotations

"""Compat shim: execution.* forwards to application.evidence.*."""

CANON_EVIDENCE_VERIFIER = True

from application.evidence.evidence_verifier import *  # noqa: F401,F403
