from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from collections.abc import Mapping, Sequence


class IntegrationMode(str, Enum):
    PLATFORM_DIRECT = "platform_direct"
    LOW_AUTONOMY = "low_autonomy"
    SUPERVISED = "supervised"
    DELEGATED_DOMAIN = "delegated_domain"
    OBSERVE_ONLY = "observe_only"
    POLICY_GUARDED_DELEGATED = "policy_guarded_delegated"


class CapabilityKind(str, Enum):
    DOMAIN_AI = "domain_ai"
    DOMAIN_PLANNER = "domain_planner"
    DOMAIN_SCHEDULER = "domain_scheduler"
    PRICING_ENGINE = "pricing_engine"
    RETENTION_ENGINE = "retention_engine"
    CONTENT_ENGINE = "content_engine"
    PAYMENT_ORCHESTRATOR = "payment_orchestrator"
    ANALYTICS_ENGINE = "analytics_engine"


class ConstraintSeverity(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class ExecutionVerdict(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    SIMULATED = "simulated"


@dataclass(frozen=True)
class PolicyConstraint:
    name: str
    value: Any
    severity: ConstraintSeverity = ConstraintSeverity.HARD
    reason: str | None = None


@dataclass(frozen=True)
class BusinessCapability:
    kind: CapabilityKind
    enabled: bool = True
    confidence: float = 1.0
    notes: str | None = None


@dataclass(frozen=True)
class BusinessGoalEnvelope:
    business_id: str
    goal_id: str
    goal_type: str
    goal_payload: Mapping[str, Any] = field(default_factory=dict)
    priority: int = 50
    requested_by: str = "platform"
    simulation: bool = False
    constraints: Sequence[PolicyConstraint] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BusinessExecutionEvidence:
    event_type: str
    payload: Mapping[str, Any]
    timestamp_utc: str
    source: str


@dataclass(frozen=True)
class BusinessExecutionResult:
    verdict: ExecutionVerdict
    business_id: str
    goal_id: str
    execution_id: str
    message: str
    metrics: Mapping[str, Any] = field(default_factory=dict)
    evidence: Sequence[BusinessExecutionEvidence] = field(default_factory=tuple)
    delegated_to_domain_engine: bool = False
    adapter_name: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BusinessExecutionRequest:
    envelope: BusinessGoalEnvelope
    integration_mode: IntegrationMode
    correlation_id: str = ""
    idempotency_key: str = ""
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        if not self.correlation_id:
            object.__setattr__(self, "correlation_id", f"exec:{self.envelope.business_id}:{self.envelope.goal_id}")
        if not self.idempotency_key:
            object.__setattr__(self, "idempotency_key", self.correlation_id)
