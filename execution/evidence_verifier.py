"""Compat shim: execution.* forwards to application.evidence.*."""

from __future__ import annotations

from application.evidence.evidence_verifier import *  # noqa: F401,F403

CANON_EVIDENCE_VERIFIER = True

