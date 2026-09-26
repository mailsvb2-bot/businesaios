from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any

from contracts.business_constraints import ConstraintSeverity


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


CANON_AGENT_IDENTITY_CONTRACT = True
AGENT_IDENTITY_SCHEMA_VERSION = 1


class AgentLifecycleStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


def _agent_token(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    if any(ord(ch) < 32 for ch in text):
        raise ValueError(f"{field_name} contains control characters")
    return text


def _agent_scope(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(_agent_token(value, "scope value") for value in values)))


def _agent_budget(values: Mapping[str, float] | None) -> Mapping[str, float]:
    normalized: dict[str, float] = {}
    for raw_key, raw_value in dict(values or {}).items():
        key = _agent_token(raw_key, "budget scope key")
        if isinstance(raw_value, bool):
            raise ValueError("budget scope values must be finite non-negative numbers")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("budget scope values must be finite non-negative numbers") from exc
        if not isfinite(value) or value < 0:
            raise ValueError("budget scope values must be finite non-negative numbers")
        normalized[key] = value
    return MappingProxyType(dict(sorted(normalized.items())))


@dataclass(frozen=True)
class AgentIdentity:
    """Canonical business-scoped identity and delegated authority envelope."""

    agent_id: str
    agent_type: str
    agent_version: str
    tenant_id: str
    business_id: str
    delegated_by: str | None = None
    policy_profile: str = "default"
    capability_scope: tuple[str, ...] = ()
    budget_scope: Mapping[str, float] = field(default_factory=dict)
    risk_scope: tuple[str, ...] = ()
    data_scope: tuple[str, ...] = ()
    lifecycle_status: AgentLifecycleStatus = AgentLifecycleStatus.ACTIVE
    schema_version: int = AGENT_IDENTITY_SCHEMA_VERSION
    created_at_ms: int = 0
    updated_at_ms: int = 0
    revoked_at_ms: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent_id", _agent_token(self.agent_id, "agent_id"))
        object.__setattr__(self, "agent_type", _agent_token(self.agent_type, "agent_type"))
        object.__setattr__(self, "agent_version", _agent_token(self.agent_version, "agent_version"))
        object.__setattr__(self, "tenant_id", _agent_token(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "business_id", _agent_token(self.business_id, "business_id"))
        object.__setattr__(
            self,
            "delegated_by",
            None if self.delegated_by is None else _agent_token(self.delegated_by, "delegated_by"),
        )
        object.__setattr__(self, "policy_profile", _agent_token(self.policy_profile, "policy_profile"))
        object.__setattr__(self, "capability_scope", _agent_scope(self.capability_scope))
        object.__setattr__(self, "budget_scope", _agent_budget(self.budget_scope))
        object.__setattr__(self, "risk_scope", _agent_scope(self.risk_scope))
        object.__setattr__(self, "data_scope", _agent_scope(self.data_scope))
        if self.schema_version != AGENT_IDENTITY_SCHEMA_VERSION:
            raise ValueError("unsupported agent identity schema_version")
        if self.created_at_ms < 0 or self.updated_at_ms < 0:
            raise ValueError("agent timestamps must be non-negative")
        if self.updated_at_ms < self.created_at_ms:
            raise ValueError("agent updated_at_ms cannot precede created_at_ms")
        if self.lifecycle_status is AgentLifecycleStatus.REVOKED:
            if self.revoked_at_ms is None:
                raise ValueError("revoked agent requires revoked_at_ms")
            if self.revoked_at_ms < self.created_at_ms:
                raise ValueError("revoked_at_ms cannot precede created_at_ms")
        elif self.revoked_at_ms is not None:
            raise ValueError("active agent cannot have revoked_at_ms")

    def revoke(self, *, at_ms: int) -> "AgentIdentity":
        when = max(int(at_ms), self.updated_at_ms)
        return replace(
            self,
            lifecycle_status=AgentLifecycleStatus.REVOKED,
            updated_at_ms=when,
            revoked_at_ms=when,
        )


def assert_delegation_within_parent(*, parent: AgentIdentity, child: AgentIdentity) -> None:
    """Fail closed if a delegated agent widens its parent's proven authority."""

    if parent.lifecycle_status is not AgentLifecycleStatus.ACTIVE:
        raise ValueError("delegating parent agent is revoked")
    if child.delegated_by != parent.agent_id:
        raise ValueError("child delegated_by does not match parent agent")
    if (child.tenant_id, child.business_id) != (parent.tenant_id, parent.business_id):
        raise ValueError("delegated agent must stay within parent tenant/business")
    if not set(child.capability_scope).issubset(parent.capability_scope):
        raise ValueError("delegated capability_scope exceeds parent authority")
    if not set(child.risk_scope).issubset(parent.risk_scope):
        raise ValueError("delegated risk_scope exceeds parent authority")
    if not set(child.data_scope).issubset(parent.data_scope):
        raise ValueError("delegated data_scope exceeds parent authority")
    for key, value in child.budget_scope.items():
        parent_value = parent.budget_scope.get(key)
        if parent_value is None or value > parent_value:
            raise ValueError("delegated budget_scope exceeds parent authority")
