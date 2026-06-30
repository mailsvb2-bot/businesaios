"""Governance boot boundary.

The previous merged state still tried to lazy-load a removed public_api module,
which made the package unimportable. Keep a direct, explicit boundary here
instead of recreating a redundant runtime facade.
"""

from __future__ import annotations

from .governance_builder import CANON_BOOT_WIRING_ONLY, GovernanceService, build_governance_service
from .governance_registration import get_governance_service, register_governance

__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "GovernanceService",
    "build_governance_service",
    "get_governance_service",
    "register_governance",
]

