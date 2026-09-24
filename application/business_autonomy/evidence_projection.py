from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol

from application.business_autonomy.channel_contracts import (
    ChannelExecutionEnvelope,
    ChannelIdentity,
    ChannelKind,
)
from application.business_autonomy.contracts import BusinessExecutionResult
from application.ontology.event_fact_lifecycle import (
    EventFactLifecycleWriter,
    business_fact_from_event,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, BusinessFactV1, EventStore, supports_event_store
from reliability.idempotency_contract import IdempotencyStore
from runtime.state import StateSynthesisEngine, StateSynthesisRequest, business_fact_to_state_observation
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_BUSINESS_AUTONOMY_EVIDENCE_PROJECTION = True


def _text(value: object) -> str:
    return str(value or "").strip()


def _payload(result: BusinessExecutionResult) -> dict:
    return {
        "message": result.message,
        "metrics": dict(result.metrics),
        "metadata": dict(result.metadata),
        "evidence": [
            {
                "event_type": item.event_type,
                "payload": dict(item.payload),
                "timestamp_utc": item.timestamp_utc,
                "source": item.source,
            }
            for item in result.evidence
        ],
    }


def _tenant_id(result: BusinessExecutionResult) -> str:
    return _text(result.metadata.get("tenant_id") or result.business_id or "global")


def project_business_autonomy_evidence(
    result: BusinessExecutionResult, *, created_at: datetime | None = None
) -> EvidenceRecord:
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    source = _text(result.adapter_name) or "business_autonomy"
    decision_ref = _text(
        result.metadata.get("decision_id") or result.metadata.get("sovereign_decision_id")
    )
    action_ref = _text(result.metadata.get("action_id")) or _text(result.goal_id)
    derived_fact_ref = _text(
        result.metadata.get("derived_fact_ref") or result.metadata.get("semantic_state_id")
    )
    execution_ref = _text(result.execution_id)
    lineage = {
        "source": source,
        "normalization": f"business-autonomy-result:{execution_ref}",
        "action": action_ref,
        "outcome": execution_ref,
    }
    if derived_fact_ref:
        lineage["derived_fact"] = derived_fact_ref
    if decision_ref:
        lineage["decision"] = decision_ref
    refs = tuple(
        dict.fromkeys(
            value
            for value in (
                source,
                _text(result.business_id),
                _text(result.goal_id),
                derived_fact_ref,
                decision_ref,
                action_ref,
            )
            if value
        )
    )
    return EvidenceRecord(
        evidence_id=f"business-autonomy:{execution_ref}",
        tenant_id=_tenant_id(result),
        scope="business_autonomy",
        run_id=execution_ref,
        action_id=action_ref,
        action_type="business_autonomy_execution",
        verification_status=result.verdict.value,
        created_at=timestamp,
        source=source,
        source_type="business_autonomy_execution",
        business_id=_text(result.business_id),
        observed_at=timestamp,
        privacy_class="internal",
        retention_policy="business_execution_evidence",
        lineage=lineage,
        refs=refs,
        payload=_payload(result),
        labels={
            "business_id": _text(result.business_id),
            "goal_id": _text(result.goal_id),
            "verdict": result.verdict.value,
        },
    ).normalized_for_write()


def append_business_autonomy_evidence(
    *, backend: EvidenceStore, result: BusinessExecutionResult
) -> EvidenceRecord:
    tenant_id = _tenant_id(result)
    evidence_id = f"business-autonomy:{_text(result.execution_id)}"
    existing = backend.get(tenant_id=tenant_id, evidence_id=evidence_id)
    record = project_business_autonomy_evidence(
        result, created_at=None if existing is None else existing.created_at
    )
    if existing is not None:
        if existing != record:
            raise ValueError("business autonomy evidence replay conflicts with canonical evidence")
        return existing
    try:
        return backend.append(record)
    except ValueError as exc:
        current = backend.get(tenant_id=tenant_id, evidence_id=evidence_id)
        if current is not None:
            replay = project_business_autonomy_evidence(result, created_at=current.created_at)
            if current == replay:
                return current
        raise ValueError("business autonomy evidence replay conflicts with canonical evidence") from exc



CANON_EXTERNAL_BUSINESS_READ_INGRESS = True
_EXTERNAL_BUSINESS_READ_SOURCE = "api_business.read"
_EXTERNAL_BUSINESS_MAX_PAYLOAD_BYTES = 262_144


@dataclass(frozen=True)
class NormalizedExternalBusinessFact:
    """Provider-neutral observation; scope and authority stay inside BusinessAIOS."""

    external_event_id: str
    fact_type: str
    entity_id: str
    payload: Mapping[str, Any]
    occurred_at_ms: int
    observed_at_ms: int
    confidence: float = 0.5
    ttl_ms: int | None = None
    valid_until_ms: int | None = None

    def normalized_payload(self) -> dict[str, Any]:
        try:
            encoded = json.dumps(
                dict(self.payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        except (TypeError, ValueError) as exc:
            raise ValueError("external business fact payload must be canonical JSON") from exc
        if len(encoded) > _EXTERNAL_BUSINESS_MAX_PAYLOAD_BYTES:
            raise ValueError("external business fact payload is too large")
        return json.loads(encoded)

    def validate(self) -> None:
        for name in ("external_event_id", "fact_type", "entity_id"):
            value = str(getattr(self, name) or "").strip()
            if not value or len(value) > 512:
                raise ValueError(f"{name} is required and must be <= 512 characters")
        if min(int(self.occurred_at_ms), int(self.observed_at_ms)) < 0:
            raise ValueError("external business fact timestamps must be >= 0")
        if int(self.observed_at_ms) < int(self.occurred_at_ms):
            raise ValueError("observed_at_ms must not precede occurred_at_ms")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.ttl_ms is not None and int(self.ttl_ms) < 0:
            raise ValueError("ttl_ms must be >= 0")
        if self.valid_until_ms is not None and int(self.valid_until_ms) < int(self.occurred_at_ms):
            raise ValueError("valid_until_ms must not precede occurred_at_ms")
        self.normalized_payload()


class ApiBusinessReadTransport(Protocol):
    async def read_fact(
        self,
        *,
        identity: ChannelIdentity,
        envelope: ChannelExecutionEnvelope,
    ) -> NormalizedExternalBusinessFact: ...


@dataclass(frozen=True)
class ExternalBusinessFactIngressResult:
    fact_id: str
    evidence_id: str
    state_id: str
    replayed: bool


class ExternalBusinessFactIngress:
    """Evidence -> canonical BusinessFact -> existing World Model; never a write capability."""

    def __init__(
        self,
        *,
        event_store: EventStore,
        evidence_store: EvidenceStore,
        state_engine: StateSynthesisEngine,
        idempotency_store: IdempotencyStore,
    ) -> None:
        if not supports_event_store(event_store):
            raise ValueError("canonical EventStore is required")
        if idempotency_store is None:
            raise ValueError("canonical IdempotencyStore is required")
        self._events = event_store
        self._evidence = evidence_store
        self._state = state_engine
        self._fact_writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="external_business_read",
            source=_EXTERNAL_BUSINESS_READ_SOURCE,
            id_prefix="external-business-fact",
        )

    async def read_and_ingest(
        self,
        *,
        transport: ApiBusinessReadTransport,
        identity: ChannelIdentity,
        envelope: ChannelExecutionEnvelope,
        correlation_id: str | None = None,
        recorded_at_ms: int | None = None,
    ) -> ExternalBusinessFactIngressResult:
        envelope.validate()
        if identity != envelope.identity:
            raise ValueError("external business read identity/envelope mismatch")
        if identity.channel_kind is not ChannelKind.API_BUSINESS:
            raise ValueError("external business read requires API_BUSINESS identity")
        if str(envelope.operation) != "api_read":
            raise ValueError("external business read requires api_read operation")
        fact = await transport.read_fact(identity=identity, envelope=envelope)
        if not isinstance(fact, NormalizedExternalBusinessFact):
            raise TypeError("external business read transport returned a non-canonical fact")
        return self.ingest(
            identity=identity,
            fact=fact,
            correlation_id=correlation_id,
            recorded_at_ms=recorded_at_ms,
        )

    def ingest(
        self,
        *,
        identity: ChannelIdentity,
        fact: NormalizedExternalBusinessFact,
        correlation_id: str | None = None,
        recorded_at_ms: int | None = None,
    ) -> ExternalBusinessFactIngressResult:
        if identity.channel_kind is not ChannelKind.API_BUSINESS:
            raise ValueError("external business fact requires API_BUSINESS identity")
        fact.validate()
        payload = fact.normalized_payload()
        idempotency_key, evidence_id = _external_business_ids(
            identity, fact.external_event_id
        )
        fact_id = self._fact_writer.fact_id_for(
            tenant_id=identity.tenant_id,
            business_id=identity.business_id,
            entity_id=str(fact.entity_id).strip(),
            operation="ingest",
            idempotency_key=idempotency_key,
            payload=payload,
        )
        recorded = max(
            int(time.time() * 1000) if recorded_at_ms is None else int(recorded_at_ms),
            int(fact.observed_at_ms),
        )
        durable = self._find_fact(identity.tenant_id, fact_id)
        replayed = durable is not None
        if durable is None:
            self._ensure_evidence(identity, fact, payload, fact_id, evidence_id, recorded)
            durable = self._append_fact(
                identity,
                fact,
                payload,
                fact_id,
                evidence_id,
                idempotency_key,
                correlation_id,
                recorded,
            )
        else:
            self._assert_fact(durable, identity, fact, payload, evidence_id)
            self._require_evidence(identity, fact, payload, fact_id, evidence_id)
            if not self._fact_writer.repair_existing(
                tenant_id=identity.tenant_id,
                business_id=identity.business_id,
                entity_id=str(fact.entity_id).strip(),
                operation="ingest",
                idempotency_key=idempotency_key,
                fact_type=str(fact.fact_type).strip(),
                payload=payload,
                event_metadata=_external_business_event_metadata(
                    fact=fact,
                    evidence_id=evidence_id,
                    correlation_id=durable.correlation_id,
                    recorded_at_ms=int(
                        durable.recorded_at_ms or durable.observed_at_ms
                    ),
                ),
            ):
                raise RuntimeError("external business durable fact lost idempotency claim")

        snapshot = self._state.synthesize(
            StateSynthesisRequest(
                tenant_id=identity.tenant_id,
                business_id=identity.business_id,
                now_ms=max(recorded, int(durable.observed_at_ms)),
                observations=(business_fact_to_state_observation(durable),),
                correlation_id=str(durable.correlation_id or correlation_id or fact_id),
                meta={
                    "ingress": _EXTERNAL_BUSINESS_READ_SOURCE,
                    "fact_id": fact_id,
                    "evidence_id": evidence_id,
                },
            )
        )
        return ExternalBusinessFactIngressResult(fact_id, evidence_id, snapshot.state_id, replayed)

    def _ensure_evidence(
        self,
        identity: ChannelIdentity,
        fact: NormalizedExternalBusinessFact,
        payload: dict[str, Any],
        fact_id: str,
        evidence_id: str,
        recorded_at_ms: int,
    ) -> None:
        existing = self._evidence.get(tenant_id=identity.tenant_id, evidence_id=evidence_id)
        created_at = (
            datetime.fromtimestamp(recorded_at_ms / 1000, tz=UTC)
            if existing is None
            else existing.created_at
        )
        expected = _external_business_evidence(
            identity, fact, payload, fact_id, evidence_id, created_at
        )
        if existing is not None:
            if existing != expected:
                raise ValueError("external business evidence replay conflicts with canonical evidence")
            return
        try:
            self._evidence.append(expected)
        except ValueError as exc:
            if self._evidence.get(tenant_id=identity.tenant_id, evidence_id=evidence_id) != expected:
                raise ValueError(
                    "external business evidence replay conflicts with canonical evidence"
                ) from exc

    def _require_evidence(
        self,
        identity: ChannelIdentity,
        fact: NormalizedExternalBusinessFact,
        payload: dict[str, Any],
        fact_id: str,
        evidence_id: str,
    ) -> None:
        existing = self._evidence.get(tenant_id=identity.tenant_id, evidence_id=evidence_id)
        if existing is None:
            raise RuntimeError("canonical external business fact references missing evidence")
        expected = _external_business_evidence(
            identity, fact, payload, fact_id, evidence_id, existing.created_at
        )
        if existing != expected:
            raise ValueError("external business evidence replay conflicts with canonical evidence")

    def _append_fact(
        self,
        identity: ChannelIdentity,
        fact: NormalizedExternalBusinessFact,
        payload: dict[str, Any],
        fact_id: str,
        evidence_id: str,
        idempotency_key: str,
        correlation_id: str | None,
        recorded_at_ms: int,
    ) -> BusinessFactV1:
        appended_id = self._fact_writer.append_once(
            tenant_id=identity.tenant_id,
            business_id=identity.business_id,
            entity_id=str(fact.entity_id).strip(),
            operation="ingest",
            idempotency_key=idempotency_key,
            fact_type=str(fact.fact_type).strip(),
            payload=payload,
            occurred_at_ms=int(fact.occurred_at_ms),
            observed_at_ms=int(fact.observed_at_ms),
            event_metadata=_external_business_event_metadata(
                fact=fact,
                evidence_id=evidence_id,
                correlation_id=correlation_id,
                recorded_at_ms=recorded_at_ms,
            ),
        )
        if appended_id != fact_id:
            raise RuntimeError("external business canonical fact identity changed")
        durable = self._find_fact(identity.tenant_id, fact_id)
        if durable is None:
            raise RuntimeError("external business EventStore append did not become durable")
        self._assert_fact(durable, identity, fact, payload, evidence_id)
        return durable

    def _find_fact(self, tenant_id: str, fact_id: str) -> BusinessFactV1 | None:
        matched = None
        for event in self._events.iter_events(
            tenant_id=str(tenant_id),
            start_ms=0,
            event_type=BUSINESS_FACT_EVENT_TYPE,
        ):
            if str(event.get("event_id") or "") != fact_id:
                continue
            if matched is not None:
                raise RuntimeError("duplicate external business fact identity in EventStore")
            matched = business_fact_from_event(dict(event))
        return matched

    @staticmethod
    def _assert_fact(
        durable: BusinessFactV1,
        identity: ChannelIdentity,
        fact: NormalizedExternalBusinessFact,
        payload: dict[str, Any],
        evidence_id: str,
    ) -> None:
        expected = _external_business_fact_event(
            identity=identity,
            fact=fact,
            payload=payload,
            fact_id=durable.fact_id,
            evidence_id=evidence_id,
            correlation_id=durable.correlation_id,
            recorded_at_ms=int(durable.recorded_at_ms or durable.observed_at_ms),
        )
        if durable.as_event() != expected:
            raise ValueError("external business event replay conflicts with canonical fact")


def _external_business_ids(
    identity: ChannelIdentity,
    external_event_id: str,
) -> tuple[str, str]:
    digest = sha256(
        "\0".join(
            (
                identity.tenant_id,
                identity.business_id,
                identity.channel_kind.value,
                str(identity.external_ref or ""),
                str(external_event_id).strip(),
            )
        ).encode()
    ).hexdigest()
    return (
        f"external-business-read:{digest}",
        f"external-business-evidence:{digest}",
    )


def _external_business_provenance(
    fact: NormalizedExternalBusinessFact,
    recorded_at_ms: int,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "confidence": float(fact.confidence),
        "authoritative": False,
        "source_priority": 50,
        "recorded_at_ms": int(recorded_at_ms),
        "valid_from_ms": int(fact.occurred_at_ms),
    }
    if fact.ttl_ms is not None:
        value["ttl_ms"] = int(fact.ttl_ms)
    if fact.valid_until_ms is not None:
        value["valid_until_ms"] = int(fact.valid_until_ms)
    return value


def _external_business_event_metadata(
    *,
    fact: NormalizedExternalBusinessFact,
    evidence_id: str,
    correlation_id: str | None,
    recorded_at_ms: int,
) -> dict[str, object]:
    return {
        "correlation_id": correlation_id,
        "recorded_at_ms": int(recorded_at_ms),
        "evidence_ids": (evidence_id,),
        "provenance": _external_business_provenance(fact, recorded_at_ms),
    }


def _external_business_fact_event(
    *,
    identity: ChannelIdentity,
    fact: NormalizedExternalBusinessFact,
    payload: dict[str, Any],
    fact_id: str,
    evidence_id: str,
    correlation_id: str | None,
    recorded_at_ms: int,
) -> dict[str, Any]:
    return {
        "event_id": fact_id,
        "tenant_id": identity.tenant_id,
        "source": _EXTERNAL_BUSINESS_READ_SOURCE,
        "event_type": BUSINESS_FACT_EVENT_TYPE,
        "timestamp_ms": int(fact.observed_at_ms),
        "decision_id": None,
        "correlation_id": correlation_id,
        "payload": {
            "schema_version": 1,
            "business_id": identity.business_id,
            "fact_type": str(fact.fact_type).strip(),
            "entity_id": str(fact.entity_id).strip(),
            "event_time_ms": int(fact.occurred_at_ms),
            "observed_at_ms": int(fact.observed_at_ms),
            "recorded_at_ms": int(recorded_at_ms),
            "actor_id": None,
            "agent_id": None,
            "causation_id": None,
            "evidence_ids": [evidence_id],
            "payload": payload,
            "provenance": _external_business_provenance(fact, recorded_at_ms),
            "supersedes_fact_id": None,
        },
    }

def _external_business_evidence(
    identity: ChannelIdentity,
    fact: NormalizedExternalBusinessFact,
    payload: dict[str, Any],
    fact_id: str,
    evidence_id: str,
    created_at: datetime,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        tenant_id=identity.tenant_id,
        scope="external_business_read",
        run_id=fact_id,
        action_type="external_business_read",
        verification_status="observed",
        created_at=created_at,
        source=_EXTERNAL_BUSINESS_READ_SOURCE,
        source_type="external_business_observation",
        business_id=identity.business_id,
        observed_at=datetime.fromtimestamp(int(fact.observed_at_ms) / 1000, tz=UTC),
        confidence=float(fact.confidence),
        privacy_class="internal",
        retention_policy="external_business_observation",
        lineage={
            "source": _EXTERNAL_BUSINESS_READ_SOURCE,
            "normalization": f"external-business-read:{fact_id}",
            "derived_fact": fact_id,
        },
        refs=(fact_id,),
        payload={
            "external_event_id": str(fact.external_event_id).strip(),
            "connection_ref": str(identity.external_ref or ""),
            "fact_type": str(fact.fact_type).strip(),
            "entity_id": str(fact.entity_id).strip(),
            "occurred_at_ms": int(fact.occurred_at_ms),
            "observed_at_ms": int(fact.observed_at_ms),
            "payload": payload,
        },
        labels={
            "fact_type": str(fact.fact_type).strip(),
            "entity_id": str(fact.entity_id).strip(),
        },
    ).normalized_for_write()


__all__ = [
    "ApiBusinessReadTransport",
    "CANON_BUSINESS_AUTONOMY_EVIDENCE_PROJECTION",
    "CANON_EXTERNAL_BUSINESS_READ_INGRESS",
    "ExternalBusinessFactIngress",
    "ExternalBusinessFactIngressResult",
    "NormalizedExternalBusinessFact",
    "append_business_autonomy_evidence",
    "project_business_autonomy_evidence",
]
