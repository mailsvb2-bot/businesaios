from __future__ import annotations

import pytest

from application.organization import OrganizationProjector, OrganizationRegistry
from contracts.organization import OrganizationNotFound, OrganizationStatus
from reliability.idempotency_contract import IdempotencyState
from reliability.idempotency_store import InMemoryIdempotencyStore, JsonlIdempotencyStore
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None):
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if int(event.get("timestamp_ms") or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)

    def count_events(self, *, tenant_id: str, start_ms: int, end_ms: int, user_id=None, event_type=None) -> int:
        return sum(1 for _ in self.iter_events(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, user_id=user_id, event_type=event_type))


class CrashOnCompletionIdempotencyStore(InMemoryIdempotencyStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_completion = False
        self.last_reserved_key = None

    def reserve(self, **kwargs):
        decision = super().reserve(**kwargs)
        self.last_reserved_key = kwargs["key"]
        return decision

    def mark_completed(self, **kwargs):
        if self.fail_next_completion:
            self.fail_next_completion = False
            raise RuntimeError("simulated crash before idempotency completion")
        return super().mark_completed(**kwargs)

    def expire_last_claim(self) -> None:
        assert self.last_reserved_key is not None
        cache_key = self.last_reserved_key.as_tuple()
        record = self._records[cache_key]
        self._records[cache_key] = record.mark_expired()


class AppendThenRaiseEventStore(MemoryEventStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_append = True

    def append_event(self, event: dict) -> None:
        super().append_event(event)
        if self.fail_next_append:
            self.fail_next_append = False
            raise RuntimeError("simulated uncertain EventStore append")


def _registry() -> tuple[OrganizationRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return OrganizationRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_organization_lifecycle_is_event_backed_idempotent_and_unknown_first() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1",
        business_id="business-1",
        organization_id="org-1",
        idempotency_key="create-1",
        occurred_at_ms=100,
    )
    assert created.name is None
    assert created.organization_type is None
    assert created.status is OrganizationStatus.ACTIVE
    assert len(events.events) == 1

    replay = registry.create(
        tenant_id="tenant-1",
        business_id="business-1",
        organization_id="org-1",
        idempotency_key="create-1",
        occurred_at_ms=100,
    )
    assert replay == created
    assert len(events.events) == 1

    updated = registry.update(
        tenant_id="tenant-1",
        business_id="business-1",
        organization_id="org-1",
        idempotency_key="update-1",
        name="Acme Operations",
        organization_type="operating_entity",
        occurred_at_ms=200,
    )
    assert updated.name == "Acme Operations"
    assert updated.organization_type == "operating_entity"
    assert updated.updated_at_ms == 200

    archived = registry.archive(
        tenant_id="tenant-1",
        business_id="business-1",
        organization_id="org-1",
        idempotency_key="archive-1",
        occurred_at_ms=300,
    )
    assert archived.status is OrganizationStatus.ARCHIVED
    assert archived.archived_at_ms == 300
    assert len(events.events) == 3


def test_organization_idempotency_key_reuse_with_different_update_fails_closed() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="create", name="One", occurred_at_ms=100,
    )
    registry.update(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="same-update", name="Two", occurred_at_ms=200,
    )
    with pytest.raises(RuntimeError, match="rejected_scope_mismatch"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
            idempotency_key="same-update", name="Three", occurred_at_ms=300,
        )


def test_organization_projection_is_tenant_and_business_scoped() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = OrganizationRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="shared",
        idempotency_key="t1", name="Tenant One", occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant-2", business_id="business-2", organization_id="shared",
        idempotency_key="t2", name="Tenant Two", occurred_at_ms=100,
    )
    projector = OrganizationProjector(events)
    assert projector.get(tenant_id="tenant-1", business_id="business-1", organization_id="shared").name == "Tenant One"
    assert projector.get(tenant_id="tenant-2", business_id="business-2", organization_id="shared").name == "Tenant Two"
    with pytest.raises(OrganizationNotFound):
        projector.get(tenant_id="tenant-1", business_id="business-2", organization_id="shared")


def test_archived_organization_rejects_update() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="create", occurred_at_ms=100,
    )
    registry.archive(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="archive", occurred_at_ms=200,
    )
    with pytest.raises(ValueError, match="archived organization"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
            idempotency_key="update", name="forbidden", occurred_at_ms=300,
        )


def test_create_repairs_crash_after_durable_fact_before_idempotency_completion() -> None:
    events = MemoryEventStore()
    claims = CrashOnCompletionIdempotencyStore()
    claims.fail_next_completion = True
    registry = OrganizationRegistry(event_store=events, idempotency_store=claims)

    with pytest.raises(RuntimeError, match="simulated crash"):
        registry.create(
            tenant_id="tenant-1", business_id="business-1", organization_id="org-crash",
            idempotency_key="create-crash", name="Recovered Org", occurred_at_ms=100,
        )
    assert len(events.events) == 1

    recovered = registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-crash",
        idempotency_key="create-crash", name="Recovered Org", occurred_at_ms=999,
    )
    assert recovered.name == "Recovered Org"
    assert recovered.created_at_ms == 100
    assert len(events.events) == 1
    assert claims.last_reserved_key is not None
    repaired = claims.get(key=claims.last_reserved_key)
    assert repaired is not None
    assert repaired.state is IdempotencyState.COMPLETED
    assert repaired.result_ref == events.events[0]["event_id"]
    assert repaired.result_digest == claims.last_reserved_key.scope_hash


def test_update_repairs_expired_claim_after_durable_fact() -> None:
    events = MemoryEventStore()
    claims = CrashOnCompletionIdempotencyStore()
    registry = OrganizationRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-expired",
        idempotency_key="create", name="Before", occurred_at_ms=100,
    )
    claims.fail_next_completion = True
    with pytest.raises(RuntimeError, match="simulated crash"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", organization_id="org-expired",
            idempotency_key="update-crash", name="After", occurred_at_ms=200,
        )
    assert len(events.events) == 2
    claims.expire_last_claim()

    recovered = registry.update(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-expired",
        idempotency_key="update-crash", name="After", occurred_at_ms=900,
    )
    assert recovered.name == "After"
    assert recovered.updated_at_ms == 200
    assert len(events.events) == 2
    assert claims.last_reserved_key is not None
    repaired = claims.get(key=claims.last_reserved_key)
    assert repaired is not None and repaired.state is IdempotencyState.COMPLETED


def test_archive_repairs_crash_without_duplicate_fact() -> None:
    events = MemoryEventStore()
    claims = CrashOnCompletionIdempotencyStore()
    registry = OrganizationRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-archive",
        idempotency_key="create", occurred_at_ms=100,
    )
    claims.fail_next_completion = True
    with pytest.raises(RuntimeError, match="simulated crash"):
        registry.archive(
            tenant_id="tenant-1", business_id="business-1", organization_id="org-archive",
            idempotency_key="archive-crash", occurred_at_ms=200,
        )
    assert len(events.events) == 2

    recovered = registry.archive(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-archive",
        idempotency_key="archive-crash", occurred_at_ms=800,
    )
    assert recovered.status is OrganizationStatus.ARCHIVED
    assert recovered.archived_at_ms == 200
    assert len(events.events) == 2


def test_uncertain_event_store_append_reconciles_existing_durable_fact() -> None:
    events = AppendThenRaiseEventStore()
    claims = InMemoryIdempotencyStore()
    registry = OrganizationRegistry(event_store=events, idempotency_store=claims)

    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-uncertain",
        idempotency_key="create-uncertain", name="Certain", occurred_at_ms=100,
    )
    assert created.name == "Certain"
    assert len(events.events) == 1


def test_completed_idempotency_claim_without_durable_fact_fails_closed() -> None:
    class MissingFactCompletedStore(InMemoryIdempotencyStore):
        def reserve(self, **kwargs):
            decision = super().reserve(**kwargs)
            if decision.resolution.value == "accepted":
                super().mark_completed(
                    key=kwargs["key"],
                    owner_id=kwargs["owner_id"],
                    result_ref="missing-fact",
                    result_digest=kwargs["key"].scope_hash,
                )
                return super().reserve(**kwargs)
            return decision

    registry = OrganizationRegistry(event_store=MemoryEventStore(), idempotency_store=MissingFactCompletedStore())
    with pytest.raises(RuntimeError, match="completed without durable fact"):
        registry.create(
            tenant_id="tenant-1", business_id="business-1", organization_id="org-missing",
            idempotency_key="missing", occurred_at_ms=100,
        )


def test_crash_recovery_survives_real_sqlite_and_idempotency_restart(tmp_path) -> None:
    class CrashOnceJsonlIdempotencyStore(JsonlIdempotencyStore):
        def __init__(self, path) -> None:
            super().__init__(path)
            self.fail_next_completion = True
            self.last_reserved_key = None

        def reserve(self, **kwargs):
            decision = super().reserve(**kwargs)
            self.last_reserved_key = kwargs["key"]
            return decision

        def mark_completed(self, **kwargs):
            if self.fail_next_completion:
                self.fail_next_completion = False
                raise RuntimeError("simulated durable crash before idempotency completion")
            return super().mark_completed(**kwargs)

    event_path = tmp_path / "organization-events.sqlite3"
    idempotency_path = tmp_path / "organization-idempotency.jsonl"
    crashing_claims = CrashOnceJsonlIdempotencyStore(idempotency_path)
    with SqliteEventStore(str(event_path)) as events:
        registry = OrganizationRegistry(event_store=events, idempotency_store=crashing_claims)
        with pytest.raises(RuntimeError, match="simulated durable crash"):
            registry.create(
                tenant_id="tenant-real", business_id="business-real", organization_id="org-real",
                idempotency_key="create-real", name="Durable Org", occurred_at_ms=123,
            )
        rows = tuple(events.iter_events(tenant_id="tenant-real", start_ms=0))
        assert len(rows) == 1
    assert crashing_claims.last_reserved_key is not None
    key = crashing_claims.last_reserved_key

    reopened_claims = JsonlIdempotencyStore(idempotency_path)
    with SqliteEventStore(str(event_path)) as events:
        recovered_registry = OrganizationRegistry(event_store=events, idempotency_store=reopened_claims)
        recovered = recovered_registry.create(
            tenant_id="tenant-real", business_id="business-real", organization_id="org-real",
            idempotency_key="create-real", name="Durable Org", occurred_at_ms=999,
        )
        assert recovered.name == "Durable Org"
        assert recovered.created_at_ms == 123
        rows = tuple(events.iter_events(tenant_id="tenant-real", start_ms=0))
        assert len(rows) == 1

    repaired = JsonlIdempotencyStore(idempotency_path).get(key=key)
    assert repaired is not None
    assert repaired.state is IdempotencyState.COMPLETED
    assert repaired.result_ref == rows[0]["event_id"]
    assert repaired.result_digest == key.scope_hash
