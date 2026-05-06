from __future__ import annotations

"""Canonical public DecisionCore surface.

This module keeps the public import path small while preserving the single-brain
invariant: the sovereign ``DecisionCore`` class still lives only in
``core.ai.decision_core``.
"""

from core.ai.decision_core import DecisionCore
from core.decision_core_contract import CANONICAL_DECISION_CORE_IMPORT_PATH

CANON_DECISION_CORE_PUBLIC_API = True

__all__ = ["CANON_DECISION_CORE_IMPORT_PATH", "CANON_DECISION_CORE_PUBLIC_API", "DecisionCore"]
