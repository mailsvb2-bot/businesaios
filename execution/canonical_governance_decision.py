from __future__ import annotations

"""Compat shim: execution.* forwards to application.governance.*."""

CANON_GOVERNANCE_DECISION_CONTRACT = True

from application.governance.canonical_governance_decision import *  # noqa: F401,F403
