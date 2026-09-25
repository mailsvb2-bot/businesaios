from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from application.business_autonomy.contracts import (
    AGENT_IDENTITY_SCHEMA_VERSION,
    AgentIdentity,
    AgentLifecycleStatus,
    BusinessCapability,
    CapabilityKind,
    assert_delegation_within_parent,
)
from application.business_autonomy.protocol import ExternalBusinessAdapter
from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_contract import IdempotencyStore


@dataclass(frozen=True)
class RegisteredBusinessCapabilities:
    business_id: str
    capabilities: Sequence[BusinessCapability]


class BusinessCapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, RegisteredBusinessCapabilities] = {}

    def register(self, business_id: str, capabilities: Sequence[BusinessCapability]) -> None:
        self._items[business_id] = RegisteredBusinessCapabilities(
            business_id=business_id,
            capabilities=tuple(capabilities),
        )

    def get(self, business_id: str) -> RegisteredBusinessCapabilities:
        try:
            return self._items[business_id]
        except KeyError as exc:
            raise KeyError(f"Capabilities not registered for business_id={business_id}") from exc

    def supports(self, business_id: str, kind: CapabilityKind) -> bool:
        entry = self.get(business_id)
        return any(item.kind == kind and item.enabled for item in entry.capabilities)

    def snapshot(self) -> Mapping[str, RegisteredBusinessCapabilities]:
        return dict(self._items)


class BusinessAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ExternalBusinessAdapter] = {}

    def register(self, adapter: ExternalBusinessAdapter) -> None:
        if adapter.business_id in self._adapters:
            raise ValueError(f"Adapter already registered for business_id={adapter.business_id}")
        self._adapters[adapter.business_id] = adapter

    def get(self, business_id: str) -> ExternalBusinessAdapter:
        try:
            return self._adapters[business_id]
        except KeyError as exc:
            raise KeyError(f"Adapter not registered for business_id={business_id}") from exc


AGENT_REGISTERED = "agent.registered"
AGENT_REVOKED = "agent.revoked"
AGENT_FACT_TYPES = frozenset({AGENT_REGISTERED, AGENT_REVOKED})
CANON_AGENT_IDENTITY_LIFECYCLE_OWNER = True
CANON_AGENT_DELEGATION_GRAPH = True


class AgentIdentityNotFound(LookupError):
    """Canonical agent identity does not exist in the requested business scope."""


class AgentIdentityHistoryInvariantViolation(RuntimeError):
    """Persisted AgentIdentity chronology violates canonical lifecycle invariants."""


class AgentIdentityProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(
        self,
        *,
        tenant_id: str,
        business_id: str,
        agent_id: str | None = None,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(
                tenant_id=str(tenant_id),
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in AGENT_FACT_TYPES:
                continue
            if str(event.get("source") or "") != "agent_identity_registry":
                raise AgentIdentityHistoryInvariantViolation(
                    "agent identity facts must come from canonical registry"
                )
            if agent_id is not None and entity_id != str(agent_id):
                continue
            rows.append(
                {
                    "fact_id": str(event.get("event_id") or ""),
                    "fact_type": fact_type,
                    "entity_id": entity_id,
                    "event_time_ms": int(
                        envelope.get("event_time_ms") or event.get("timestamp_ms") or 0
                    ),
                    "append_order": append_order,
                    "payload": dict(envelope.get("payload") or {}),
                }
            )
        rows.sort(key=lambda row: (int(row["append_order"]), str(row["fact_id"])))
        return rows

    @staticmethod
    def _identity_from_create(
        *,
        tenant_id: str,
        business_id: str,
        agent_id: str,
        event_time_ms: int,
        payload: dict[str, object],
    ) -> AgentIdentity:
        if payload.get("schema_version") != AGENT_IDENTITY_SCHEMA_VERSION:
            raise AgentIdentityHistoryInvariantViolation(
                "agent identity history has unsupported schema_version"
            )
        try:
            return AgentIdentity(
                agent_id=agent_id,
                agent_type=str(payload.get("agent_type") or ""),
                agent_version=str(payload.get("agent_version") or ""),
                tenant_id=tenant_id,
                business_id=business_id,
                delegated_by=(
                    None
                    if payload.get("delegated_by") is None
                    else str(payload.get("delegated_by") or "")
                ),
                policy_profile=str(payload.get("policy_profile") or ""),
                capability_scope=tuple(payload.get("capability_scope") or ()),
                budget_scope=dict(payload.get("budget_scope") or {}),
                risk_scope=tuple(payload.get("risk_scope") or ()),
                data_scope=tuple(payload.get("data_scope") or ()),
                created_at_ms=event_time_ms,
                updated_at_ms=event_time_ms,
            )
        except (TypeError, ValueError) as exc:
            raise AgentIdentityHistoryInvariantViolation(
                "agent identity registered payload is invalid"
            ) from exc

    def get(self, *, tenant_id: str, business_id: str, agent_id: str) -> AgentIdentity:
        facts = self._facts(
            tenant_id=tenant_id,
            business_id=business_id,
            agent_id=agent_id,
        )
        if not facts:
            raise AgentIdentityNotFound(f"agent identity not found: {agent_id}")
        created_rows = [row for row in facts if row["fact_type"] == AGENT_REGISTERED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise AgentIdentityHistoryInvariantViolation(
                "agent identity history must begin with exactly one registration"
            )
        created = created_rows[0]
        identity = self._identity_from_create(
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            agent_id=str(agent_id),
            event_time_ms=int(created["event_time_ms"]),
            payload=dict(created["payload"]),
        )
        for row in facts[1:]:
            if identity.lifecycle_status is AgentLifecycleStatus.REVOKED:
                raise AgentIdentityHistoryInvariantViolation(
                    "agent identity history continues after revocation"
                )
            if row["fact_type"] != AGENT_REVOKED:
                raise AgentIdentityHistoryInvariantViolation(
                    "agent identity history contains unknown transition"
                )
            payload = dict(row["payload"])
            if payload.get("schema_version") != AGENT_IDENTITY_SCHEMA_VERSION:
                raise AgentIdentityHistoryInvariantViolation(
                    "agent identity revocation schema_version is invalid"
                )
            identity = identity.revoke(at_ms=int(row["event_time_ms"]))
        return identity

    def list_for_business(
        self,
        *,
        tenant_id: str,
        business_id: str,
        include_revoked: bool = False,
    ) -> tuple[AgentIdentity, ...]:
        ids = sorted(
            {
                str(row["entity_id"])
                for row in self._facts(tenant_id=tenant_id, business_id=business_id)
                if row["fact_type"] == AGENT_REGISTERED
            }
        )
        identities = tuple(
            self.get(tenant_id=tenant_id, business_id=business_id, agent_id=agent_id)
            for agent_id in ids
        )
        return tuple(
            identity
            for identity in identities
            if include_revoked
            or identity.lifecycle_status is AgentLifecycleStatus.ACTIVE
        )


class AgentIdentityRegistry:
    """Single AgentIdentity/delegation lifecycle writer over the canonical EventStore."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = AgentIdentityProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="agent_identity_fact",
            source="agent_identity_registry",
            id_prefix="agent-identity",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        when = int(time.time() * 1000) if value is None else int(value)
        if when < 0:
            raise ValueError("agent identity timestamp cannot be negative")
        return when

    @staticmethod
    def _payload(identity: AgentIdentity) -> dict[str, object]:
        return {
            "schema_version": AGENT_IDENTITY_SCHEMA_VERSION,
            "agent_type": identity.agent_type,
            "agent_version": identity.agent_version,
            "delegated_by": identity.delegated_by,
            "policy_profile": identity.policy_profile,
            "capability_scope": list(identity.capability_scope),
            "budget_scope": dict(identity.budget_scope),
            "risk_scope": list(identity.risk_scope),
            "data_scope": list(identity.data_scope),
        }

    @staticmethod
    def _state_token(identity: AgentIdentity) -> str:
        return "|".join(
            (
                identity.lifecycle_status.value,
                str(identity.updated_at_ms),
                identity.agent_id,
                identity.agent_version,
            )
        )

    def register(
        self,
        *,
        tenant_id: str,
        business_id: str,
        agent_id: str,
        idempotency_key: str,
        agent_type: str,
        agent_version: str,
        delegated_by: str | None = None,
        policy_profile: str = "default",
        capability_scope: tuple[str, ...] = (),
        budget_scope: dict[str, float] | None = None,
        risk_scope: tuple[str, ...] = (),
        data_scope: tuple[str, ...] = (),
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> AgentIdentity:
        when = self._time(occurred_at_ms)
        candidate = AgentIdentity(
            agent_id=agent_id,
            agent_type=agent_type,
            agent_version=agent_version,
            tenant_id=tenant_id,
            business_id=business_id,
            delegated_by=delegated_by,
            policy_profile=policy_profile,
            capability_scope=capability_scope,
            budget_scope=dict(budget_scope or {}),
            risk_scope=risk_scope,
            data_scope=data_scope,
            created_at_ms=when,
            updated_at_ms=when,
        )
        if candidate.delegated_by is not None:
            if candidate.delegated_by == candidate.agent_id:
                raise ValueError("agent cannot delegate to itself")
            parent = self._projector.get(
                tenant_id=candidate.tenant_id,
                business_id=candidate.business_id,
                agent_id=candidate.delegated_by,
            )
            assert_delegation_within_parent(parent=parent, child=candidate)

        payload = self._payload(candidate)
        try:
            current = self._projector.get(
                tenant_id=candidate.tenant_id,
                business_id=candidate.business_id,
                agent_id=candidate.agent_id,
            )
        except AgentIdentityNotFound:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError(
                    "agent identity already exists with different immutable authority"
                )
            repaired = self._writer.repair_existing(
                tenant_id=candidate.tenant_id,
                business_id=candidate.business_id,
                entity_id=candidate.agent_id,
                operation="register",
                idempotency_key=idempotency_key,
                fact_type=AGENT_REGISTERED,
                payload=payload,
                event_metadata=event_metadata,
            )
            if not repaired:
                raise ValueError(
                    "agent identity already exists and registration key does not match"
                )
            return current

        self._writer.append_once(
            tenant_id=candidate.tenant_id,
            business_id=candidate.business_id,
            entity_id=candidate.agent_id,
            operation="register",
            idempotency_key=idempotency_key,
            fact_type=AGENT_REGISTERED,
            payload=payload,
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(
            tenant_id=candidate.tenant_id,
            business_id=candidate.business_id,
            agent_id=candidate.agent_id,
        )

    def revoke(
        self,
        *,
        tenant_id: str,
        business_id: str,
        agent_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> AgentIdentity:
        current = self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            agent_id=agent_id,
        )
        payload = {"schema_version": AGENT_IDENTITY_SCHEMA_VERSION}
        if current.lifecycle_status is AgentLifecycleStatus.REVOKED:
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=agent_id,
                operation="revoke",
                idempotency_key=idempotency_key,
                fact_type=AGENT_REVOKED,
                payload=payload,
                event_metadata=event_metadata,
            )
            if not repaired:
                raise ValueError("agent is already revoked under another idempotency key")
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=agent_id,
            expected_state_token=self._state_token(current),
            operation="revoke",
            idempotency_key=idempotency_key,
            fact_type=AGENT_REVOKED,
            payload=payload,
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            agent_id=agent_id,
        )

    def get(self, *, tenant_id: str, business_id: str, agent_id: str) -> AgentIdentity:
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            agent_id=agent_id,
        )

    def assert_active(
        self,
        *,
        tenant_id: str,
        business_id: str,
        agent_id: str,
    ) -> AgentIdentity:
        identity = self.get(
            tenant_id=tenant_id,
            business_id=business_id,
            agent_id=agent_id,
        )
        if identity.lifecycle_status is not AgentLifecycleStatus.ACTIVE:
            raise PermissionError("agent identity is revoked")
        return identity

    def assert_execution_authorized(
        self,
        *,
        tenant_id: str,
        business_id: str,
        agent_id: str,
        capability: str,
    ) -> AgentIdentity:
        """Re-authorize the complete delegation chain for a new side effect."""

        current = self.assert_active(
            tenant_id=tenant_id,
            business_id=business_id,
            agent_id=agent_id,
        )
        required_capability = str(capability or "").strip()
        if not required_capability:
            raise PermissionError("execution capability is required")
        if required_capability not in current.capability_scope:
            raise PermissionError("agent capability is not delegated")

        seen: set[str] = set()
        cursor = current
        while True:
            if cursor.agent_id in seen:
                raise PermissionError("agent delegation cycle detected")
            seen.add(cursor.agent_id)
            if cursor.lifecycle_status is not AgentLifecycleStatus.ACTIVE:
                raise PermissionError("agent delegation chain contains revoked identity")
            if required_capability not in cursor.capability_scope:
                raise PermissionError("delegation chain no longer authorizes capability")
            if cursor.delegated_by is None:
                return current
            parent = self.assert_active(
                tenant_id=tenant_id,
                business_id=business_id,
                agent_id=cursor.delegated_by,
            )
            assert_delegation_within_parent(parent=parent, child=cursor)
            cursor = parent

    def list_for_business(
        self,
        *,
        tenant_id: str,
        business_id: str,
        include_revoked: bool = False,
    ) -> tuple[AgentIdentity, ...]:
        return self._projector.list_for_business(
            tenant_id=tenant_id,
            business_id=business_id,
            include_revoked=include_revoked,
        )
