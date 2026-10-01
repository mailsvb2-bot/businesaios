from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from application.business_discovery.contracts import (
    DiscoveryFieldSpec,
    discovery_field_spec,
    normalize_discovery_value,
)
from application.ontology.event_fact_lifecycle import (
    EventFactLifecycleWriter,
    business_fact_from_event,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, BusinessFactV1, EventStore, supports_event_store
from reliability.idempotency_contract import IdempotencyStore
from runtime.state import StateSynthesisEngine, StateSynthesisRequest
from runtime.state.state_contract import StateEvidenceRef, StateObservation, StateSynthesizedSnapshot
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_BUSINESS_DISCOVERY_OWNER_ASSERTION_INGRESS = True
_OWNER_ASSERTION_SOURCE = "business_discovery.owner_assertion"
_OWNER_ASSERTION_SOURCE_PRIORITY = 40
_OWNER_ASSERTION_CONFIDENCE = 0.5
_OWNER_ASSERTION_MAX_PAYLOAD_BYTES = 65_536


def _required(value: object, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _json_value(value: Any) -> Any:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("business discovery assertion value must be canonical JSON") from exc
    if len(encoded) > _OWNER_ASSERTION_MAX_PAYLOAD_BYTES:
        raise ValueError("business discovery assertion payload is too large")
    return json.loads(encoded.decode("utf-8"))


@dataclass(frozen=True)
class OwnerBusinessAssertion:
    tenant_id: str
    business_id: str
    actor_id: str
    field_key: str
    value: Any
    observed_at_ms: int
    occurred_at_ms: int | None = None
    unknown: bool = False
    correlation_id: str | None = None

    def validate(self) -> DiscoveryFieldSpec:
        _required(self.tenant_id, "tenant_id")
        _required(self.business_id, "business_id")
        _required(self.actor_id, "actor_id")
        spec = discovery_field_spec(self.field_key)
        if int(self.observed_at_ms) <= 0:
            raise ValueError("observed_at_ms must be > 0")
        occurred = self.observed_at_ms if self.occurred_at_ms is None else int(self.occurred_at_ms)
        if occurred <= 0:
            raise ValueError("occurred_at_ms must be > 0")
        if occurred > int(self.observed_at_ms):
            raise ValueError("occurred_at_ms must not follow observed_at_ms")
        if self.unknown:
            if self.value not in (None, ""):
                raise ValueError("unknown assertion must not carry a concrete value")
        else:
            _json_value(normalize_discovery_value(spec, self.value))
        return spec

    def normalized_value(self) -> Any:
        spec = self.validate()
        if self.unknown:
            return None
        return _json_value(normalize_discovery_value(spec, self.value))


@dataclass(frozen=True)
class OwnerAssertionIngressResult:
    fact_id: str
    evidence_id: str
    state_id: str
    field_path: str
    replayed: bool


class OwnerBusinessAssertionIngress:
    """Owner assertion -> Evidence -> BusinessFact -> semantic state.

    The durable truth history stays in the canonical Event/Evidence stores.
    Current-state materialization is delegated to StateSynthesisEngine; this
    component owns neither a profile database nor a second World Model.
    """

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
        if state_engine.snapshot_store is None:
            raise ValueError("canonical durable StateSnapshotStore is required")
        self._events = event_store
        self._evidence = evidence_store
        self._state = state_engine
        self._fact_writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="business_discovery.owner_assertion",
            source=_OWNER_ASSERTION_SOURCE,
            id_prefix="business-discovery-owner-fact",
        )

    def ingest(
        self,
        *,
        assertion: OwnerBusinessAssertion,
        idempotency_key: str,
        recorded_at_ms: int | None = None,
    ) -> OwnerAssertionIngressResult:
        spec = assertion.validate()
        user_key = _required(idempotency_key, "idempotency_key")
        tenant_id = _required(assertion.tenant_id, "tenant_id")
        business_id = _required(assertion.business_id, "business_id")
        actor_id = _required(assertion.actor_id, "actor_id")
        value = assertion.normalized_value()
        payload = {
            "schema_version": 1,
            "field_key": spec.key,
            "field_path": spec.field_path,
            "value": value,
            "unknown": bool(assertion.unknown),
            "epistemic_status": "OWNER_ASSERTED",
        }
        occurred_at_ms = int(
            assertion.observed_at_ms
            if assertion.occurred_at_ms is None
            else assertion.occurred_at_ms
        )
        observed_at_ms = int(assertion.observed_at_ms)
        recorded = int(time.time() * 1000) if recorded_at_ms is None else int(recorded_at_ms)
        if recorded <= 0:
            raise ValueError("recorded_at_ms must be > 0")
        if observed_at_ms > recorded:
            raise ValueError("observed_at_ms must not follow recorded_at_ms")
        correlation_id = str(assertion.correlation_id or "").strip() or None

        existing_for_key = self._find_existing_key_binding(
            tenant_id=tenant_id,
            business_id=business_id,
            idempotency_key=user_key,
        )
        replayed = existing_for_key is not None
        if existing_for_key is not None:
            durable = business_fact_from_event(existing_for_key)
            if (
                str(durable.actor_id or "") != actor_id
                or durable.fact_type != spec.fact_type
                or dict(durable.payload) != payload
                or int(durable.event_time_ms) != occurred_at_ms
                or int(durable.observed_at_ms) != observed_at_ms
            ):
                raise ValueError(
                    "business discovery idempotency key is already bound to a different assertion"
                )
            if not self._fact_writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=business_id,
                operation="assert",
                idempotency_key=user_key,
                fact_type=durable.fact_type,
                payload=dict(durable.payload),
                event_metadata={"actor_id": actor_id},
            ):
                raise RuntimeError("business discovery durable fact lost idempotency claim")
            evidence_id = _evidence_id(durable.fact_id)
            self._require_evidence(
                durable=durable,
                evidence_id=evidence_id,
                field_spec=spec,
                value=value,
                unknown=bool(assertion.unknown),
            )
        else:
            fact_id = self._fact_writer.fact_id_for(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=business_id,
                operation="assert",
                idempotency_key=user_key,
                payload=payload,
            )
            evidence_id = _evidence_id(fact_id)
            self._ensure_evidence(
                assertion=assertion,
                field_spec=spec,
                fact_id=fact_id,
                evidence_id=evidence_id,
                payload=payload,
                recorded_at_ms=recorded,
            )
            appended_id = self._fact_writer.append_once(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=business_id,
                operation="assert",
                idempotency_key=user_key,
                fact_type=spec.fact_type,
                payload=payload,
                occurred_at_ms=occurred_at_ms,
                observed_at_ms=observed_at_ms,
                event_metadata={
                    "actor_id": actor_id,
                    "correlation_id": correlation_id,
                    "recorded_at_ms": recorded,
                    "evidence_ids": (evidence_id,),
                    "provenance": _owner_provenance(recorded, occurred_at_ms),
                },
            )
            if appended_id != fact_id:
                raise RuntimeError("business discovery canonical fact identity changed")
            durable = self._find_fact(tenant_id=tenant_id, fact_id=fact_id)
            if durable is None:
                raise RuntimeError("business discovery EventStore append did not become durable")

        base_snapshot = self._state.snapshot_store.load_latest(
            tenant_id=tenant_id,
            business_id=business_id,
        )
        if replayed and base_snapshot is not None:
            projected_field = base_snapshot.fields.get(spec.field_path)
            projected_fact_id = (
                str(projected_field.meta.get("business_discovery_fact_id") or "")
                if projected_field is not None
                else ""
            )
            if projected_fact_id == durable.fact_id:
                return OwnerAssertionIngressResult(
                    fact_id=durable.fact_id,
                    evidence_id=evidence_id,
                    state_id=base_snapshot.state_id,
                    field_path=spec.field_path,
                    replayed=True,
                )

        snapshot = self._project_fact(
            durable=durable,
            field_spec=spec,
            evidence_id=evidence_id,
            base_snapshot=base_snapshot,
        )
        return OwnerAssertionIngressResult(
            fact_id=durable.fact_id,
            evidence_id=evidence_id,
            state_id=snapshot.state_id,
            field_path=spec.field_path,
            replayed=replayed,
        )

    def _project_fact(
        self,
        *,
        durable: BusinessFactV1,
        field_spec: DiscoveryFieldSpec,
        evidence_id: str,
        base_snapshot: StateSynthesizedSnapshot | None,
    ) -> StateSynthesizedSnapshot:
        provenance = dict(durable.provenance)
        payload = dict(durable.payload)
        observation = StateObservation(
            field_path=field_spec.field_path,
            value=payload.get("value"),
            source=str(durable.source),
            observed_at_ms=int(durable.observed_at_ms),
            occurred_at_ms=int(durable.event_time_ms),
            recorded_at_ms=int(durable.recorded_at_ms or durable.observed_at_ms),
            confidence=float(provenance.get("confidence", _OWNER_ASSERTION_CONFIDENCE)),
            authoritative=bool(provenance.get("authoritative", False)),
            source_priority=int(provenance.get("source_priority", _OWNER_ASSERTION_SOURCE_PRIORITY)),
            valid_from_ms=int(provenance.get("valid_from_ms", durable.event_time_ms)),
            unknown=bool(payload.get("unknown")),
            evidence_refs=(
                StateEvidenceRef(
                    evidence_id=evidence_id,
                    kind="owner_assertion",
                    observed_at_ms=int(durable.observed_at_ms),
                    meta={
                        "fact_id": durable.fact_id,
                        "actor_id": str(durable.actor_id or ""),
                    },
                ),
            ),
            semantic_kind="fact",
            tenant_id=durable.tenant_id,
            business_id=durable.business_id,
            meta={
                "business_discovery_fact_id": durable.fact_id,
                "business_discovery_field_key": field_spec.key,
                "epistemic_status": "OWNER_ASSERTED",
                "actor_id": str(durable.actor_id or ""),
            },
        )
        return self._state.synthesize(
            StateSynthesisRequest(
                tenant_id=durable.tenant_id,
                business_id=durable.business_id,
                now_ms=max(
                    int(durable.recorded_at_ms or durable.observed_at_ms),
                    int(durable.observed_at_ms),
                ),
                observations=(observation,),
                base_snapshot=base_snapshot,
                correlation_id=str(durable.correlation_id or durable.fact_id),
                meta={
                    "ingress": _OWNER_ASSERTION_SOURCE,
                    "fact_id": durable.fact_id,
                    "evidence_id": evidence_id,
                    "field_key": field_spec.key,
                },
            )
        )

    def _find_existing_key_binding(
        self,
        *,
        tenant_id: str,
        business_id: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        matched: dict[str, Any] | None = None
        for raw_event in self._events.iter_events(
            tenant_id=tenant_id,
            start_ms=0,
            event_type=BUSINESS_FACT_EVENT_TYPE,
        ):
            event = dict(raw_event)
            envelope = dict(event.get("payload") or {})
            if str(event.get("source") or "") != _OWNER_ASSERTION_SOURCE:
                continue
            if str(envelope.get("business_id") or "") != business_id:
                continue
            if str(envelope.get("entity_id") or "") != business_id:
                continue
            persisted_payload = dict(envelope.get("payload") or {})
            expected_id = self._fact_writer.fact_id_for(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=business_id,
                operation="assert",
                idempotency_key=idempotency_key,
                payload=persisted_payload,
            )
            if str(event.get("event_id") or "") != expected_id:
                continue
            if matched is not None:
                raise RuntimeError(
                    "multiple business discovery facts match one idempotency key"
                )
            matched = event
        return matched

    def _find_fact(self, *, tenant_id: str, fact_id: str) -> BusinessFactV1 | None:
        matched: BusinessFactV1 | None = None
        for event in self._events.iter_events(
            tenant_id=tenant_id,
            start_ms=0,
            event_type=BUSINESS_FACT_EVENT_TYPE,
        ):
            if str(event.get("event_id") or "") != fact_id:
                continue
            if matched is not None:
                raise RuntimeError("duplicate business discovery fact identity")
            matched = business_fact_from_event(dict(event))
        return matched

    def _ensure_evidence(
        self,
        *,
        assertion: OwnerBusinessAssertion,
        field_spec: DiscoveryFieldSpec,
        fact_id: str,
        evidence_id: str,
        payload: dict[str, Any],
        recorded_at_ms: int,
    ) -> None:
        existing = self._evidence.get(
            tenant_id=assertion.tenant_id,
            evidence_id=evidence_id,
        )
        created_at = (
            datetime.fromtimestamp(recorded_at_ms / 1000, tz=UTC)
            if existing is None
            else existing.created_at
        )
        expected = _owner_evidence(
            assertion=assertion,
            field_spec=field_spec,
            fact_id=fact_id,
            evidence_id=evidence_id,
            payload=payload,
            created_at=created_at,
        )
        if existing is not None:
            if existing != expected:
                raise ValueError(
                    "business discovery evidence replay conflicts with canonical evidence"
                )
            return
        try:
            self._evidence.append(expected)
        except ValueError as exc:
            current = self._evidence.get(
                tenant_id=assertion.tenant_id,
                evidence_id=evidence_id,
            )
            if current != expected:
                raise ValueError(
                    "business discovery evidence replay conflicts with canonical evidence"
                ) from exc

    def _require_evidence(
        self,
        *,
        durable: BusinessFactV1,
        evidence_id: str,
        field_spec: DiscoveryFieldSpec,
        value: Any,
        unknown: bool,
    ) -> None:
        existing = self._evidence.get(
            tenant_id=durable.tenant_id,
            evidence_id=evidence_id,
        )
        if existing is None:
            raise RuntimeError(
                "canonical business discovery fact references missing evidence"
            )
        assertion = OwnerBusinessAssertion(
            tenant_id=durable.tenant_id,
            business_id=durable.business_id,
            actor_id=str(durable.actor_id or ""),
            field_key=field_spec.key,
            value=value,
            observed_at_ms=int(durable.observed_at_ms),
            occurred_at_ms=int(durable.event_time_ms),
            unknown=unknown,
            correlation_id=durable.correlation_id,
        )
        expected = _owner_evidence(
            assertion=assertion,
            field_spec=field_spec,
            fact_id=durable.fact_id,
            evidence_id=evidence_id,
            payload=dict(durable.payload),
            created_at=existing.created_at,
        )
        if existing != expected:
            raise ValueError(
                "business discovery evidence replay conflicts with canonical evidence"
            )


def _evidence_id(fact_id: str) -> str:
    digest = sha256(str(fact_id).encode("utf-8")).hexdigest()
    return f"business-discovery-owner-evidence:{digest}"


def _owner_provenance(recorded_at_ms: int, occurred_at_ms: int) -> dict[str, Any]:
    return {
        "epistemic_status": "OWNER_ASSERTED",
        "confidence": _OWNER_ASSERTION_CONFIDENCE,
        "authoritative": False,
        "source_priority": _OWNER_ASSERTION_SOURCE_PRIORITY,
        "recorded_at_ms": int(recorded_at_ms),
        "valid_from_ms": int(occurred_at_ms),
    }


def _owner_evidence(
    *,
    assertion: OwnerBusinessAssertion,
    field_spec: DiscoveryFieldSpec,
    fact_id: str,
    evidence_id: str,
    payload: dict[str, Any],
    created_at: datetime,
) -> EvidenceRecord:
    observed_at = datetime.fromtimestamp(int(assertion.observed_at_ms) / 1000, tz=UTC)
    return EvidenceRecord(
        evidence_id=evidence_id,
        tenant_id=_required(assertion.tenant_id, "tenant_id"),
        scope="business_discovery",
        run_id=fact_id,
        action_type="owner_business_assertion",
        verification_status="asserted",
        created_at=created_at,
        source=_OWNER_ASSERTION_SOURCE,
        source_type="owner_assertion",
        business_id=_required(assertion.business_id, "business_id"),
        observed_at=observed_at,
        confidence=_OWNER_ASSERTION_CONFIDENCE,
        privacy_class="internal",
        retention_policy="business_discovery_assertion",
        lineage={
            "source": _OWNER_ASSERTION_SOURCE,
            "normalization": f"business-discovery:{fact_id}",
            "derived_fact": fact_id,
        },
        refs=(fact_id,),
        payload={
            "actor_id": _required(assertion.actor_id, "actor_id"),
            "field_key": field_spec.key,
            "field_path": field_spec.field_path,
            "fact_type": field_spec.fact_type,
            "assertion": payload,
        },
        labels={
            "field_key": field_spec.key,
            "domain": field_spec.domain,
            "epistemic_status": "OWNER_ASSERTED",
        },
    ).normalized_for_write()


CANON_BUSINESS_DISCOVERY_PROVIDER_OBSERVATION_INGRESS = True
_PROVIDER_EVIDENCE_IDS_META = "business_discovery_provider_evidence_ids"
_PROVIDER_SOURCE_PRIORITY = 90
_PROVIDER_CONFIDENCE = 1.0
_ALLOWED_OBSERVATION_KEYS = frozenset({"field_key", "value", "unknown"})


@dataclass(frozen=True)
class ProviderObservationIngressResult:
    evidence_id: str
    state_id: str
    observed_fields: tuple[str, ...]
    verified_fields: tuple[str, ...]
    conflicted_fields: tuple[str, ...]
    replayed: bool


class ProviderBusinessObservationIngress:
    """Live provider Evidence -> canonical StateSynthesis reconciliation."""

    def __init__(
        self,
        *,
        event_store: EventStore,
        evidence_store: EvidenceStore,
        state_engine: StateSynthesisEngine,
    ) -> None:
        if not supports_event_store(event_store):
            raise ValueError("canonical EventStore is required")
        if state_engine.snapshot_store is None:
            raise ValueError("canonical durable StateSnapshotStore is required")
        self._events = event_store
        self._evidence = evidence_store
        self._state = state_engine

    def reconcile(
        self,
        *,
        tenant_id: str,
        business_id: str,
        evidence_id: str,
    ) -> ProviderObservationIngressResult:
        tenant = _required(tenant_id, "tenant_id")
        business = _required(business_id, "business_id")
        evidence_key = _required(evidence_id, "evidence_id")
        evidence = self._evidence.get(tenant_id=tenant, evidence_id=evidence_key)
        if evidence is None:
            raise LookupError("provider evidence not found")
        self._assert_live_provider_evidence(evidence=evidence, business_id=business)

        rows = self._business_observations(evidence)
        base_snapshot = self._state.snapshot_store.load_latest(
            tenant_id=tenant,
            business_id=business,
        )
        already_seen = {
            str(item)
            for item in (
                ()
                if base_snapshot is None
                else base_snapshot.meta.get(_PROVIDER_EVIDENCE_IDS_META, ())
            )
            if str(item)
        }

        owner_by_key: dict[str, StateObservation | None] = {}
        provider_observations: list[StateObservation] = []
        verified_fields: list[str] = []
        conflicted_fields: list[str] = []
        observed_fields: list[str] = []
        for spec, value, unknown in rows:
            owner = self._latest_owner_observation(
                tenant_id=tenant,
                business_id=business,
                spec=spec,
            )
            owner_by_key[spec.key] = owner
            relation = _provider_relation(owner=owner, value=value, unknown=unknown)
            if relation == "VERIFIED":
                verified_fields.append(spec.key)
            elif relation == "CONFLICTED":
                conflicted_fields.append(spec.key)
            observed_fields.append(spec.key)
            provider_observations.append(
                self._provider_observation(
                    evidence=evidence,
                    spec=spec,
                    value=value,
                    unknown=unknown,
                    relation=relation,
                )
            )

        if evidence_key in already_seen and base_snapshot is not None:
            return ProviderObservationIngressResult(
                evidence_id=evidence_key,
                state_id=base_snapshot.state_id,
                observed_fields=tuple(observed_fields),
                verified_fields=tuple(verified_fields),
                conflicted_fields=tuple(conflicted_fields),
                replayed=True,
            )

        candidates: list[StateObservation] = []
        for spec, _, _ in rows:
            owner = owner_by_key[spec.key]
            if owner is not None:
                candidates.append(owner)
        candidates.extend(provider_observations)

        observed_ms = _datetime_ms(evidence.observed_at)
        recorded_ms = _datetime_ms(evidence.created_at)
        now_ms = max(
            observed_ms,
            recorded_ms,
            0 if base_snapshot is None else int(base_snapshot.synthesized_at_ms),
        )
        previous_meta = {} if base_snapshot is None else dict(base_snapshot.meta)
        seen = tuple(sorted({*already_seen, evidence_key}))
        snapshot = self._state.synthesize(
            StateSynthesisRequest(
                tenant_id=tenant,
                business_id=business,
                now_ms=now_ms,
                observations=tuple(candidates),
                base_snapshot=base_snapshot,
                correlation_id=f"business-discovery-provider:{evidence_key}",
                meta={
                    **previous_meta,
                    "ingress": "business_discovery.provider_observation",
                    _PROVIDER_EVIDENCE_IDS_META: seen,
                },
            )
        )
        return ProviderObservationIngressResult(
            evidence_id=evidence_key,
            state_id=snapshot.state_id,
            observed_fields=tuple(observed_fields),
            verified_fields=tuple(verified_fields),
            conflicted_fields=tuple(conflicted_fields),
            replayed=False,
        )

    @staticmethod
    def _assert_live_provider_evidence(
        *,
        evidence: EvidenceRecord,
        business_id: str,
    ) -> None:
        if str(evidence.business_id) != str(business_id):
            raise LookupError("provider evidence not found")
        if evidence.source_type != "provider_sync":
            raise ValueError("business discovery reconciliation requires provider_sync evidence")
        if evidence.verification_status != "accepted":
            raise ValueError("business discovery reconciliation requires accepted provider evidence")
        provider_key = str(evidence.source or "").strip()
        if not provider_key:
            raise ValueError("provider evidence source is required")
        payload = dict(evidence.payload or {})
        labels = dict(evidence.labels or {})
        if payload.get("accepted") is not True:
            raise ValueError("provider evidence must bind accepted=true")
        if str(payload.get("mode") or "") != "live" or str(labels.get("mode") or "") != "live":
            raise ValueError("business discovery reconciliation requires live provider evidence")
        operation = str(payload.get("operation") or "").strip()
        if not operation or str(labels.get("operation") or "") != operation:
            raise ValueError("provider evidence operation binding is invalid")
        if str(labels.get("provider_key") or "") != provider_key:
            raise ValueError("provider evidence source binding is invalid")
        if evidence.observed_at is None:
            raise ValueError("provider evidence observed_at is required")

    @staticmethod
    def _business_observations(
        evidence: EvidenceRecord,
    ) -> tuple[tuple[DiscoveryFieldSpec, Any, bool], ...]:
        payload = dict(evidence.payload or {})
        metadata = payload.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ValueError("provider evidence metadata is required")
        raw = metadata.get("business_observations")
        if not isinstance(raw, list | tuple) or not raw:
            raise ValueError("provider evidence has no canonical business observations")
        normalized: list[tuple[DiscoveryFieldSpec, Any, bool]] = []
        seen_fields: set[str] = set()
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("provider business observation must be an object")
            unknown_keys = sorted(set(item) - _ALLOWED_OBSERVATION_KEYS)
            if unknown_keys:
                raise ValueError(
                    "unsupported provider business observation fields: "
                    + ",".join(unknown_keys)
                )
            spec = discovery_field_spec(str(item.get("field_key") or ""))
            if spec.key in seen_fields:
                raise ValueError("provider evidence contains duplicate business discovery field")
            seen_fields.add(spec.key)
            unknown = item.get("unknown", False)
            if not isinstance(unknown, bool):
                raise ValueError("provider business observation unknown must be boolean")
            value = item.get("value")
            if unknown:
                if value not in (None, ""):
                    raise ValueError("unknown provider observation must not carry a concrete value")
                normalized_value = None
            else:
                normalized_value = normalize_discovery_value(spec, value)
            normalized.append((spec, normalized_value, bool(unknown)))
        return tuple(normalized)

    def _latest_owner_observation(
        self,
        *,
        tenant_id: str,
        business_id: str,
        spec: DiscoveryFieldSpec,
    ) -> StateObservation | None:
        candidates = []
        for raw_event in self._events.iter_events(
            tenant_id=tenant_id,
            start_ms=0,
            event_type=BUSINESS_FACT_EVENT_TYPE,
        ):
            event = dict(raw_event)
            if str(event.get("source") or "") != _OWNER_ASSERTION_SOURCE:
                continue
            durable = business_fact_from_event(event)
            if durable.business_id != business_id or durable.fact_type != spec.fact_type:
                continue
            payload = dict(durable.payload)
            if str(payload.get("field_key") or "") != spec.key:
                continue
            candidates.append(durable)
        if not candidates:
            return None
        durable = max(
            candidates,
            key=lambda item: (
                int(item.observed_at_ms),
                int(item.event_time_ms),
                int(item.recorded_at_ms or 0),
                str(item.fact_id),
            ),
        )
        payload = dict(durable.payload)
        provenance = dict(durable.provenance)
        return StateObservation(
            field_path=spec.field_path,
            value=payload.get("value"),
            source=str(durable.source),
            observed_at_ms=int(durable.observed_at_ms),
            occurred_at_ms=int(durable.event_time_ms),
            recorded_at_ms=int(durable.recorded_at_ms or durable.observed_at_ms),
            confidence=float(provenance.get("confidence", 0.5)),
            authoritative=bool(provenance.get("authoritative", False)),
            source_priority=int(provenance.get("source_priority", 40)),
            valid_from_ms=int(provenance.get("valid_from_ms", durable.event_time_ms)),
            unknown=bool(payload.get("unknown")),
            evidence_refs=tuple(
                StateEvidenceRef(
                    evidence_id=str(item),
                    kind="owner_assertion",
                    observed_at_ms=int(durable.observed_at_ms),
                    meta={"fact_id": durable.fact_id},
                )
                for item in durable.evidence_ids
            ),
            semantic_kind="fact",
            tenant_id=durable.tenant_id,
            business_id=durable.business_id,
            meta={
                "business_discovery_fact_id": durable.fact_id,
                "business_discovery_field_key": spec.key,
                "epistemic_status": "OWNER_ASSERTED",
                "actor_id": str(durable.actor_id or ""),
            },
        )

    @staticmethod
    def _provider_observation(
        *,
        evidence: EvidenceRecord,
        spec: DiscoveryFieldSpec,
        value: Any,
        unknown: bool,
        relation: str,
    ) -> StateObservation:
        observed_at_ms = _datetime_ms(evidence.observed_at)
        recorded_at_ms = _datetime_ms(evidence.created_at)
        payload = dict(evidence.payload or {})
        provider_key = str(evidence.source)
        return StateObservation(
            field_path=spec.field_path,
            value=value,
            source=f"provider:{provider_key}",
            observed_at_ms=observed_at_ms,
            occurred_at_ms=observed_at_ms,
            recorded_at_ms=recorded_at_ms,
            confidence=_PROVIDER_CONFIDENCE,
            authoritative=True,
            source_priority=_PROVIDER_SOURCE_PRIORITY,
            valid_from_ms=observed_at_ms,
            unknown=unknown,
            evidence_refs=(
                StateEvidenceRef(
                    evidence_id=evidence.evidence_id,
                    kind="provider_observation",
                    observed_at_ms=observed_at_ms,
                    meta={
                        "provider_key": provider_key,
                        "operation": str(payload.get("operation") or ""),
                    },
                ),
            ),
            semantic_kind="fact",
            tenant_id=evidence.tenant_id,
            business_id=evidence.business_id,
            meta={
                "business_discovery_field_key": spec.key,
                "epistemic_status": relation,
                "observation_role": "PROVIDER_OBSERVED",
                "provider_key": provider_key,
                "provider_evidence_id": evidence.evidence_id,
                "provider_operation": str(payload.get("operation") or ""),
                "provider_mode": "live",
            },
        )


def _provider_relation(*, owner: StateObservation | None, value: Any, unknown: bool) -> str:
    if owner is None:
        return "PROVIDER_OBSERVED"
    if bool(owner.unknown) == bool(unknown) and owner.value == value:
        return "VERIFIED"
    return "CONFLICTED"


def _datetime_ms(value: object) -> int:
    if value is None or not hasattr(value, "timestamp"):
        raise ValueError("provider evidence timestamp is required")
    return int(value.timestamp() * 1000)

__all__ = [
    "CANON_BUSINESS_DISCOVERY_OWNER_ASSERTION_INGRESS",
    "CANON_BUSINESS_DISCOVERY_PROVIDER_OBSERVATION_INGRESS",
    "OwnerAssertionIngressResult",
    "OwnerBusinessAssertion",
    "OwnerBusinessAssertionIngress",
    "ProviderBusinessObservationIngress",
    "ProviderObservationIngressResult",
]
