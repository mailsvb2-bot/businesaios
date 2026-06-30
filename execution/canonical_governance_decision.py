"""Compat shim: execution.* forwards to application.governance.*."""

from __future__ import annotations

from application.governance.canonical_governance_decision import *  # noqa: F401,F403

CANON_GOVERNANCE_DECISION_CONTRACT = True

