from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from contracts.action_impact_contract import ActionCategory

CANON_OPERATIONAL_ACTION_SPEC = True


@dataclass(frozen=True)
class ActionCostPolicy:
    model: str = "none"
    fixed_cost_minor: int = 0
    payload_budget_key: str | None = None
    payload_amount_key: str | None = None
    payload_unit_count_key: str | None = None
    unit_cost_minor: int = 0

    def validate(self) -> None:
        allowed = {"none", "fixed", "payload_budget", "payload_amount", "fixed_per_unit"}
        if str(self.model) not in allowed:
            raise ValueError(f"unsupported model: {self.model}")
        if int(self.fixed_cost_minor) < 0:
            raise ValueError("fixed_cost_minor must be >= 0")
        if int(self.unit_cost_minor) < 0:
            raise ValueError("unit_cost_minor must be >= 0")


@dataclass(frozen=True)
class ActionOperationalSpec:
    action_name: str
    category: ActionCategory
    is_publication: bool = False
    is_outbound: bool = False
    is_strategic: bool = False
    is_rollback_event: bool = False
    requires_human_approval: bool = False
    publication_count: int = 0
    outbound_count: int = 0
    rollback_event_count: int = 0
    payload_publication_count_key: str | None = None
    payload_outbound_count_key: str | None = None
    cost_policy: ActionCostPolicy = field(default_factory=ActionCostPolicy)
    dimensions: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.action_name or "").strip():
            raise ValueError("action_name is required")
        if int(self.publication_count) < 0:
            raise ValueError("publication_count must be >= 0")
        if int(self.outbound_count) < 0:
            raise ValueError("outbound_count must be >= 0")
        if int(self.rollback_event_count) < 0:
            raise ValueError("rollback_event_count must be >= 0")
        self.cost_policy.validate()


__all__ = [
    "ActionCostPolicy",
    "ActionOperationalSpec",
]