from __future__ import annotations

from runtime.governance import PolicyState

CANON_BOOT_WIRING_ONLY = True


class GovernanceService:
    def __init__(self, *, policy_state: PolicyState) -> None:
        self._policy_state = policy_state

    def policy_state(self) -> PolicyState:
        return self._policy_state


def build_governance_service(*, policy_state: PolicyState) -> GovernanceService:
    return GovernanceService(policy_state=policy_state)


__all__ = ["GovernanceService", "build_governance_service", "CANON_BOOT_WIRING_ONLY"]
