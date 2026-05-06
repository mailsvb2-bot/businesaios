from __future__ import annotations

"""Compat shim: bootstrap.* forwards to ports.*."""

CANON_WORLD_MODEL_CONTRACT_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True

from ports.world_model import DecisionWorldModelPort, WORLD_MODEL_CANON_VERSION

__all__ = ['DecisionWorldModelPort', 'WORLD_MODEL_CANON_VERSION', 'CANON_WORLD_MODEL_CONTRACT_FINAL_OWNER', 'CANON_BOOT_WIRING_ONLY']
