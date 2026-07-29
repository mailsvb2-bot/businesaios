"""Backward-compatible pure re-export of the canonical Autopilot contract."""

from __future__ import annotations

from contracts.autopilot_contract import (
    AutopilotCapabilities,
    AutopilotConstraints,
    AutopilotContract,
    ControlSurface,
    DataRequirements,
    SafetyPolicy,
)

CANON_COMPAT_SHIM = True

__all__ = [
    "AutopilotCapabilities",
    "AutopilotConstraints",
    "AutopilotContract",
    "ControlSurface",
    "DataRequirements",
    "SafetyPolicy",
]
