"""Compatibility import surface for sovereign decision contracts.

The semantic contract truth lives in ``contracts.decisioning``.  This module is
kept so existing imports remain stable while the canonical owner is the shared
contracts namespace.
"""

from __future__ import annotations

from contracts.decisioning.sovereign_decision_contract import (
    CANON_DECISION_CONTRACTS,
    Decision,
    DecisionEnvelope,
)

__all__ = ["CANON_DECISION_CONTRACTS", "Decision", "DecisionEnvelope"]
