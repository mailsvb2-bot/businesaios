from __future__ import annotations

from runtime.governance import PolicyState
from .governance_builder import build_governance_service

CANON_BOOT_WIRING_ONLY = True

_registered_services: dict[str, object] = {}


def register_governance(*, policy_state: PolicyState) -> None:
    """Register governance service via a thin builder-only boot unit."""
    service = build_governance_service(policy_state=policy_state)
    _registered_services["governance_service"] = service


def get_governance_service() -> object:
    return _registered_services.get("governance_service")
