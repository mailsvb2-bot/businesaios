from __future__ import annotations

"""Compatibility re-export for legacy demand_guardrails imports.

Canonical owner: guardrails/demand_policies.py
"""

from guardrails.demand_policies import NoMonopolyGuard

CANON_COMPAT_SHIM = True
CANON_TRANSITION_SURFACE = True

__all__ = ["NoMonopolyGuard", "CANON_COMPAT_SHIM", "CANON_TRANSITION_SURFACE"]
