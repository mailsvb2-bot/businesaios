from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.business_discovery.contracts import (
    DiscoveryFieldSpec,
    discovery_field_spec,
    normalize_discovery_value,
)
from application.ontology.event_fact_lifecycle import business_fact_from_event
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, EventStore, supports_event_store
from runtime.state import StateSynthesisEngine, StateSynthesisRequest
from runtime.state.state_contract import StateEvidenceRef, StateObservation
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_BUSINESS_DISCOVERY_PROVIDER_OBSERVATION_INGRESS = True
_OWNER_ASSERTION_SOURCE = "business_discovery.owner_assertion"
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
        if not isinstance(raw, (list, tuple)) or not raw:
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


def _required(value: object, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


__all__ = [
    "CANON_BUSINESS_DISCOVERY_PROVIDER_OBSERVATION_INGRESS",
    "ProviderBusinessObservationIngress",
    "ProviderObservationIngressResult",
]
