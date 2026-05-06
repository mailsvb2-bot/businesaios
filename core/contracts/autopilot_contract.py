from __future__ import annotations

"""Backward-compatible re-export.

Canonical location is top-level `contracts.autopilot_contract` to satisfy layering rules.
"""

import contracts.autopilot_contract as _autopilot_contract
from contracts.autopilot_contract import AutopilotCapabilities, AutopilotContract

CANON_COMPAT_SHIM = True
__all__ = getattr(_autopilot_contract, "__all__", ["AutopilotCapabilities", "AutopilotContract"])
