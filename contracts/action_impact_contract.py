from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


CANON_ACTION_IMPACT_CONTRACT = True


class ActionCategory(str, Enum):
    SAFE_READ = "safe_read"
    INTERNAL_WRITE = "internal_write"
    PUBLICATION = "publication"
    OUTBOUND = "outbound"
    BUDGET_CHANGE = "budget_change"
    STRATEGIC_CHANGE = "strategic_change"
    ROLLBACK = "rollback"
    EXECUTION = "execution"
    UNKNOWN = "unknown"


class CostSource(str, Enum):
    NONE = "none"
    DECLARED = "declared"
    TARIFF = "tariff"
    SPEND_MODEL = "spend_model"
    FIXED_TABLE = "fixed_table"
    HEURISTIC = "heuristic"


@dataclass(frozen=True)
class ActionImpactPolicyRef:
    policy_key: str
    version: str = "v1"

    def validate(self) -> None:
        if not str(self.policy_key or "").strip():
            raise ValueError("policy_key is required")
        if not str(self.version or "").strip():
            raise ValueError("version is required")


@dataclass(frozen=True)
class ActionImpact:
    action_name: str
    category: ActionCategory
    cost_minor: int = 0
    publication_count: int = 0
    outbound_count: int = 0
    strategic_change_count: int = 0
    rollback_event_count: int = 0
    requires_human_approval: bool = False
    cost_source: CostSource = CostSource.NONE
    confidence: float = 1.0
    policy_ref: ActionImpactPolicyRef | None = None
    dimensions: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.action_name or "").strip():
            raise ValueError("action_name is required")
        if int(self.cost_minor) < 0:
            raise ValueError("cost_minor must be >= 0")
        if int(self.publication_count) < 0:
            raise ValueError("publication_count must be >= 0")
        if int(self.outbound_count) < 0:
            raise ValueError("outbound_count must be >= 0")
        if int(self.strategic_change_count) < 0:
            raise ValueError("strategic_change_count must be >= 0")
        if int(self.rollback_event_count) < 0:
            raise ValueError("rollback_event_count must be >= 0")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.policy_ref is not None:
            self.policy_ref.validate()


@dataclass(frozen=True)
class ActionExecutionContext:
    tenant_id: str
    user_id: str | None
    action_name: str
    payload: Mapping[str, object]
    metadata: Mapping[str, object] = field(default_factory=dict)
    execution_id: str | None = None

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.action_name or "").strip():
            raise ValueError("action_name is required")


__all__ = [
    "ActionCategory",
    "ActionExecutionContext",
    "ActionImpact",
    "ActionImpactPolicyRef",
    "CostSource",
]