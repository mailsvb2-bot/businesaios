from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


SELF_DRIVING_GOVERNANCE_CONTRACT_VERSION = "SDG-CONTRACT-V2"


class GovernedEvolutionPort(Protocol):
    def evolve(self) -> bool: ...


class GovernedApprovalPort(Protocol):
    def approve(self, old: Any, new: Any) -> bool: ...


class GovernedConstitutionPort(Protocol):
    def assert_safe_evolution(self, is_safe: bool) -> None: ...


class GovernedSurvivalPort(Protocol):
    def should_rollback(self) -> bool: ...


@dataclass(frozen=True)
class GovernedEvolutionRequest:
    tenant_id: str
    loop_id: str
    requested_by: str = "system"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.loop_id or "").strip():
            raise ValueError("loop_id is required")
        if not str(self.requested_by or "").strip():
            raise ValueError("requested_by is required")


@dataclass(frozen=True)
class GovernedEvolutionReport:
    evolved: bool
    reason: str
    approval_required: bool = True
    approved: bool = False
    rollback_triggered: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)


__all__ = [
    "GovernedApprovalPort",
    "GovernedConstitutionPort",
    "GovernedEvolutionPort",
    "GovernedEvolutionReport",
    "GovernedEvolutionRequest",
    "GovernedSurvivalPort",
    "SELF_DRIVING_GOVERNANCE_CONTRACT_VERSION",
]
