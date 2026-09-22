from __future__ import annotations

from copy import deepcopy

import pytest

from application.business_autonomy.channel_contracts import (
    ChannelExecutionEnvelope,
    ChannelIdentity,
    ChannelKind,
)
from application.business_autonomy.evidence_projection import (
    ExternalBusinessFactIngress,
    NormalizedExternalBusinessFact,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, canonical_business_event_contract
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
from runtime.state import FileStateSnapshotStore, StateSynthesisEngine
from storage.evidence_store import InMemoryEvidenceStore


class _MemoryEventStore:
    def __init__(self) -> None:
        self.events: dict[str, dict] = {}

    def append_event(self, event: dict) -> None:
        event_id = str(event["event_id"])
        existing = self.events.get(event_id)
        if existing is not None and existing != event:
            raise ValueError("event_id conflict")
        self.events[event_id] = deepcopy(event)

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms: int | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
    ):
        del user_id
        for event in self.events.values():
            if event["tenant_id"] != tenant_id:
                continue
            if event_type is not None and event["event_type"] != event_type:
                continue
            timestamp = int(event["timestamp_ms"])
            if timestamp < start_ms or (end_ms is not None and timestamp > end_ms):
                continue
            yield deepcopy(event)

    def count_events(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms: int,
        user_id: str | None = None,
        event_type: str | None = None,
    ) -> int:
        return sum(
            1
            for _ in self.iter_events(
                tenant_id=tenant_id,
                start_ms=start_ms,
                end_ms=end_ms,
                user_id=user_id,
                event_type=event_type,
            )
        )


class _ReadTransport:
    def __init__(
        self,
        fact: NormalizedExternalBusinessFact,
        *,
        expected_business_id: str | None = "biz-ext-1",
    ) -> None:
        self.fact = fact
        self.expected_business_id = expected_business_id
        self.calls = 0

    async def read_fact(self, *, identity, envelope):
        self.calls += 1
        if self.expected_business_id is not None:
            assert identity.business_id == self.expected_business_id
        assert envelope.operation == "api_read"
        return self.fact


def _identity(*, business_id: str = "biz-ext-1") -> ChannelIdentity:
    return ChannelIdentity(
        business_id=business_id,
        tenant_id="tenant-ext-1",
        channel_kind=ChannelKind.API_BUSINESS,
        adapter_key="api.live",
        external_ref="external-system-1",
        region="global",
    )


def _envelope(identity: ChannelIdentity | None = None) -> ChannelExecutionEnvelope:
    return ChannelExecutionEnvelope(
        identity=identity or _identity(),
        route_key="external-business-read",
        operation="api_read",
        payload={"resource": "orders"},
    )


def _fact(*, payload: dict | None = None) -> NormalizedExternalBusinessFact:
    return NormalizedExternalBusinessFact(
        external_event_id="external-event-1",
        fact_type="order.observed",
        entity_id="order-42",
        payload=payload or {"status": "paid", "amount_minor": 12500},
        occurred_at_ms=1_000,
        observed_at_ms=1_100,
        confidence=0.8,
        ttl_ms=60_000,
    )


def _service(tmp_path):
    events = _MemoryEventStore()
    evidence = InMemoryEvidenceStore()
    snapshots = FileStateSnapshotStore(tmp_path / "state")
    service = ExternalBusinessFactIngress(
        event_store=events,
        evidence_store=evidence,
        state_engine=StateSynthesisEngine(snapshot_store=snapshots),
        idempotency_store=InMemoryIdempotencyStore(),
    )
    return service, events, evidence, snapshots


@pytest.mark.asyncio
async def test_read_only_external_business_fact_reaches_evidence_event_spine_and_world_model(
    tmp_path,
) -> None:
    service, events, evidence, snapshots = _service(tmp_path)
    transport = _ReadTransport(_fact())

    result = await service.read_and_ingest(
        transport=transport,
        identity=_identity(),
        envelope=_envelope(),
        correlation_id="corr-external-read-1",
        recorded_at_ms=1_200,
    )

    assert transport.calls == 1
    assert result.replayed is False
    assert len(events.events) == 1
    durable_event = next(iter(events.events.values()))
    assert durable_event["event_type"] == BUSINESS_FACT_EVENT_TYPE
    contract = canonical_business_event_contract(durable_event)
    assert contract["business_id"] == "biz-ext-1"
    assert contract["event_type"] == "order.observed"
    assert contract["evidence_ids"] == (result.evidence_id,)

    evidence_record = evidence.get(
        tenant_id="tenant-ext-1",
        evidence_id=result.evidence_id,
    )
    assert evidence_record is not None
    assert evidence_record.business_id == "biz-ext-1"
    assert evidence_record.lineage["derived_fact"] == result.fact_id

    snapshot = snapshots.load_latest(
        tenant_id="tenant-ext-1",
        business_id="biz-ext-1",
    )
    assert snapshot is not None
    assert snapshot.state_id == result.state_id
    assert snapshot.semantic_view is not None
    record = next(
        item for item in snapshot.semantic_view.records if result.evidence_id in item.evidence_refs
    )
    assert record.epistemic_type == "fact"
    assert record.authoritative is False
    assert record.value["payload"]["status"] == "paid"
    assert record.evidence_refs == (result.evidence_id,)


@pytest.mark.asyncio
async def test_external_business_read_replay_is_idempotent_and_does_not_duplicate_truth(
    tmp_path,
) -> None:
    service, events, evidence, _ = _service(tmp_path)
    transport = _ReadTransport(_fact())

    first = await service.read_and_ingest(
        transport=transport,
        identity=_identity(),
        envelope=_envelope(),
        recorded_at_ms=1_200,
    )
    second = await service.read_and_ingest(
        transport=transport,
        identity=_identity(),
        envelope=_envelope(),
        recorded_at_ms=2_000,
    )

    assert first.fact_id == second.fact_id
    assert first.evidence_id == second.evidence_id
    assert second.replayed is True
    assert len(events.events) == 1
    assert len(evidence.list_for_tenant(tenant_id="tenant-ext-1")) == 1


@pytest.mark.asyncio
async def test_same_external_event_cannot_silently_change_payload(tmp_path) -> None:
    service, events, _, _ = _service(tmp_path)
    identity = _identity()

    await service.read_and_ingest(
        transport=_ReadTransport(_fact()),
        identity=identity,
        envelope=_envelope(identity),
        recorded_at_ms=1_200,
    )
    with pytest.raises(ValueError, match="replay conflicts"):
        await service.read_and_ingest(
            transport=_ReadTransport(_fact(payload={"status": "refunded"})),
            identity=identity,
            envelope=_envelope(identity),
            recorded_at_ms=1_300,
        )
    assert len(events.events) == 1


@pytest.mark.asyncio
async def test_read_ingress_rejects_scope_or_operation_before_external_transport(tmp_path) -> None:
    service, _, _, _ = _service(tmp_path)
    transport = _ReadTransport(_fact())

    foreign_identity = _identity(business_id="other-business")
    with pytest.raises(ValueError, match="identity/envelope mismatch"):
        await service.read_and_ingest(
            transport=transport,
            identity=foreign_identity,
            envelope=_envelope(_identity()),
            recorded_at_ms=1_200,
        )
    assert transport.calls == 0

    wrong_operation = ChannelExecutionEnvelope(
        identity=_identity(),
        route_key="external-business-write",
        operation="api_call",
        payload={"action": "mutate"},
    )
    with pytest.raises(ValueError, match="api_read"):
        await service.read_and_ingest(
            transport=transport,
            identity=_identity(),
            envelope=wrong_operation,
            recorded_at_ms=1_200,
        )
    assert transport.calls == 0



@pytest.mark.asyncio
async def test_production_bootstrap_reads_for_registered_business_through_same_canonical_ingress(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(
        business_id="external_business",
        seed_admin_read_model=True,
    )
    transport = _ReadTransport(_fact(), expected_business_id="external_business")
    try:
        result = await service.read_external_business_fact(
            transport=transport,
            tenant_id="tenant-demo",
            business_id="external_business",
            payload={"resource": "orders"},
            correlation_id="corr-production-read",
            recorded_at_ms=1_200,
        )
        assert transport.calls == 1
        assert result.replayed is False
        events = tuple(
            service._ontology_event_store.iter_events(
                tenant_id="tenant-demo",
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        )
        assert any(str(event.get("event_id") or "") == result.fact_id for event in events)
        snapshot = service._external_business_fact_ingress._state.snapshot_store.load_latest(
            tenant_id="tenant-demo",
            business_id="external_business",
        )
        assert snapshot is not None
        assert snapshot.state_id == result.state_id
        assert snapshot.semantic_view is not None
        assert any(result.evidence_id in item.evidence_refs for item in snapshot.semantic_view.records)
    finally:
        finalizer = getattr(service, "_ontology_event_store_finalizer", None)
        if callable(finalizer):
            finalizer()
