from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

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
        store = ClientOutcomeCycleIdempotencyStore(
            backend=ClientOutcomePersistenceOwner.default().registry('client_outcome_cycle_idempotency')
        )
        try:
            return store.reserve(
                tenant_id='tenant-a',
                business_id='business-a',
                lead_id='lead-a',
                idempotency_key='idem-a',
                now=now,
                request_payload=payload,
            )['acquired']
        except RuntimeError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(reserve, range(8)))
    assert outcomes.count(True) == 1
    assert outcomes.count('client_outcome_idempotency_in_progress') == 7

    store = ClientOutcomeCycleIdempotencyStore(
        backend=ClientOutcomePersistenceOwner.default().registry('client_outcome_cycle_idempotency')
    )
    store.complete(
        tenant_id='tenant-a',
        business_id='business-a',
        lead_id='lead-a',
        idempotency_key='idem-a',
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


def test_sqlite_profile_fails_closed_for_multiple_replicas(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv('WEB_CONCURRENCY', '2')
    with pytest.raises(RuntimeError, match='EXTERNAL_STORE_REQUIRED'):
        ClientOutcomePersistenceOwner.default()
