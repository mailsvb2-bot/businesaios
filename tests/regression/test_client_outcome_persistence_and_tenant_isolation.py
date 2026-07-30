from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from entrypoints.api.client_outcome_models import SelectClientOutcomePackageRequest
from entrypoints.api.client_outcome_route_handlers import build_client_outcome_route_handlers
from lead_outcomes.client_outcome_cycle_idempotency_store import ClientOutcomeCycleIdempotencyStore
from runtime.platform.client_outcome_persistence import ClientOutcomePersistenceOwner


def _configure(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('BUSINESAIOS_CLIENT_OUTCOME_DB_PATH', str(tmp_path / 'client-outcome.sqlite3'))
    monkeypatch.delenv('BUSINESAIOS_REPLICA_COUNT', raising=False)
    monkeypatch.delenv('WEB_CONCURRENCY', raising=False)
    monkeypatch.delenv('UVICORN_WORKERS', raising=False)


def _persistent_store(*, lease_ttl_seconds: int = 900) -> ClientOutcomeCycleIdempotencyStore:
    return ClientOutcomeCycleIdempotencyStore(
        backend=ClientOutcomePersistenceOwner.default().registry('client_outcome_cycle_idempotency'),
        lease_ttl_seconds=lease_ttl_seconds,
    )


def test_client_outcome_order_survives_runtime_rebuild_and_is_tenant_scoped(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    first = build_client_outcome_route_handlers()
    created = first.select_package(
        now=datetime.now(timezone.utc),
        request=SelectClientOutcomePackageRequest(
            tenant_id='tenant-a',
            business_id='business-a',
            package_id='clients-5',
            requested_clients=5,
        ),
    )

    rebuilt = build_client_outcome_route_handlers()
    assert rebuilt.get_order(order_id=created.order_id, tenant_id='tenant-a').found is True
    assert rebuilt.get_order(order_id=created.order_id, tenant_id='tenant-b').found is False
    assert rebuilt.get_lifecycle(order_id=created.order_id, lead_id='lead-a', tenant_id='tenant-a').found is False
    with pytest.raises(PermissionError, match='tenant_mismatch'):
        rebuilt.get_lifecycle(order_id=created.order_id, lead_id='lead-a', tenant_id='tenant-b')


def test_full_cycle_idempotency_is_reserved_atomically_before_effect(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    now = datetime.now(timezone.utc)
    payload = {'tenant_id': 'tenant-a', 'business_id': 'business-a', 'lead': {'lead_id': 'lead-a'}}

    def reserve(_index: int):
        store = _persistent_store()
        try:
            return store.reserve(
                tenant_id='tenant-a',
                business_id='business-a',
                lead_id='lead-a',
                idempotency_key='idem-a',
                now=now,
                request_payload=payload,
            )
        except RuntimeError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(reserve, range(8)))
    acquired = [item for item in outcomes if isinstance(item, dict) and item.get('acquired') is True]
    assert len(acquired) == 1
    assert outcomes.count('client_outcome_idempotency_in_progress') == 7
    assert acquired[0]['recovered'] is False
    assert acquired[0]['lease_generation'] == 1
    assert acquired[0]['lease_token']

    store = _persistent_store()
    store.complete(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='idem-a',
        lease_token=acquired[0]['lease_token'],
        now=now,
        request_payload=payload,
        response_payload={'ok': True},
    )
    replay = store.reserve(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='idem-a',
        now=now,
        request_payload=payload,
    )
    assert replay['acquired'] is False
    assert replay['response'] == {'ok': True}
    with pytest.raises(ValueError, match='payload_collision'):
        store.reserve(
            tenant_id='tenant-a',
            business_id='business-a',
            lead_id='lead-a',
            idempotency_key='idem-a',
            now=now,
            request_payload={'different': True},
        )


def test_expired_idempotency_lease_is_reclaimed_once_and_fences_stale_worker(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    started_at = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    retry_at = started_at + timedelta(seconds=31)
    payload = {'tenant_id': 'tenant-a', 'business_id': 'business-a', 'lead': {'lead_id': 'lead-a'}}

    initial = _persistent_store(lease_ttl_seconds=30).reserve(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='recoverable-idem',
        now=started_at,
        request_payload=payload,
    )

    def reclaim(_index: int):
        store = _persistent_store(lease_ttl_seconds=30)
        try:
            return store.reserve(
                tenant_id='tenant-a',
                business_id='business-a',
                lead_id='lead-a',
                idempotency_key='recoverable-idem',
                now=retry_at,
                request_payload=payload,
            )
        except RuntimeError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(reclaim, range(8)))

    recovered = [item for item in outcomes if isinstance(item, dict) and item.get('acquired') is True]
    assert len(recovered) == 1
    assert outcomes.count('client_outcome_idempotency_in_progress') == 7
    winner = recovered[0]
    assert winner['recovered'] is True
    assert winner['lease_generation'] == 2
    assert winner['lease_token'] != initial['lease_token']

    store = _persistent_store(lease_ttl_seconds=30)
    with pytest.raises(RuntimeError, match='fence_violation'):
        store.complete(
            tenant_id='tenant-a',
            business_id='business-a',
            lead_id='lead-a',
            idempotency_key='recoverable-idem',
            lease_token=initial['lease_token'],
            now=retry_at,
            request_payload=payload,
            response_payload={'worker': 'stale'},
        )

    store.complete(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='recoverable-idem',
        lease_token=winner['lease_token'],
        now=retry_at,
        request_payload=payload,
        response_payload={'worker': 'winner'},
    )
    replay = store.reserve(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='recoverable-idem',
        now=retry_at,
        request_payload=payload,
    )
    assert replay['response'] == {'worker': 'winner'}


def test_legacy_reserved_row_without_lease_fields_can_be_recovered(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    started_at = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    payload = {'tenant_id': 'tenant-a', 'business_id': 'business-a', 'lead': {'lead_id': 'lead-a'}}
    store = _persistent_store(lease_ttl_seconds=30)
    initial = store.reserve(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='legacy-idem',
        now=started_at,
        request_payload=payload,
    )
    key = store.make_key(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='legacy-idem',
    )
    legacy = dict(store.get(key))
    legacy.pop('lease_token')
    legacy.pop('lease_generation')
    legacy.pop('lease_expires_at')
    store.register(key, legacy)

    recovered = _persistent_store(lease_ttl_seconds=30).reserve(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='legacy-idem',
        now=started_at + timedelta(seconds=31),
        request_payload=payload,
    )
    assert recovered['acquired'] is True
    assert recovered['recovered'] is True
    assert recovered['lease_generation'] == 2
    assert recovered['lease_token'] != initial['lease_token']


def test_sqlite_profile_fails_closed_for_multiple_replicas(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv('WEB_CONCURRENCY', '2')
    with pytest.raises(RuntimeError, match='EXTERNAL_STORE_REQUIRED'):
        ClientOutcomePersistenceOwner.default()
