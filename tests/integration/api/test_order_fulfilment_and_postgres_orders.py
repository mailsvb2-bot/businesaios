from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from contracts.order import OrderLifecycleStatus
from lead_outcomes.client_outcome_order_store import OrderStore
from runtime.platform.client_outcome_persistence import ClientOutcomePersistenceOwner
from runtime.platform.client_outcome_postgres_registry import PostgresJsonRegistryBackend
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from tests.integration.api.test_phase18_commercial_order_journey import buy, make_service

RECEIPT = {"source": "telegram", "receipt_id": "msg-1"}


def _paid(service, scope, invoices, pid):
    first = buy(service, scope, pid)
    invoices.record_payment(**scope, invoice_id=first.invoice_id, idempotency_key="all", amount_minor=85000)
    return first


def _fulfil(service, scope, order_id, *, psp=True, reversed_payment=False, evidence=RECEIPT):
    return service.record_fulfilment(
        **scope, order_id=order_id, delivery_evidence=evidence,
        payment_evidence_reader=lambda **_: psp, reversal_reader=lambda **_: reversed_payment,
        occurred_at_ms=4_000_000_000_000,
    )


def test_fulfilment_requires_receipt_and_verified_payment_then_keeps_access():
    service, scope, pid, _offers, orders, invoices, _leads = make_service()
    first = buy(service, scope, pid)
    with pytest.raises(ValueError, match="not_ready:invoice_not_paid"):
        _fulfil(service, scope, first.order_id)
    invoices.record_payment(**scope, invoice_id=first.invoice_id, idempotency_key="all", amount_minor=85000)
    with pytest.raises(ValueError, match="delivery_evidence_required"):
        _fulfil(service, scope, first.order_id, evidence={"source": "telegram"})
    with pytest.raises(ValueError, match="psp_not_verified"):
        _fulfil(service, scope, first.order_id, psp=False)
    done = _fulfil(service, scope, first.order_id)
    assert done.lifecycle_status is OrderLifecycleStatus.FULFILLED
    ready = service.execution_readiness(**scope, order_id=first.order_id,
                                        payment_evidence_reader=lambda **_: True, reversal_reader=lambda **_: False)
    assert ready.eligible
    reversed_ = service.execution_readiness(**scope, order_id=first.order_id,
                                            payment_evidence_reader=lambda **_: True, reversal_reader=lambda **_: True)
    assert reversed_.reason == "payment_reversed_or_disputed"


class _SqlitePgPort:
    """Executes the backend's PostgreSQL SQL on sqlite (same ON CONFLICT/RETURNING dialect)."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    @contextmanager
    def transaction(self):
        try:
            yield self
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()

    def _run(self, sql, params=None):
        sql = sql.replace("%s", "?").replace("BIGINT", "INTEGER")
        if sql.strip().startswith("CREATE"):
            self.conn.executescript(sql)
            return self.conn.cursor()
        return self.conn.execute(sql, params or ())

    def execute(self, sql, params=None):
        self._run(sql, params)

    def fetchone(self, sql, params=None):
        return self._run(sql, params).fetchone()

    def fetchall(self, sql, params=None):
        return self._run(sql, params).fetchall()


def _pg_backend(namespace="order"):
    conn = sqlite3.connect(":memory:")
    return PostgresJsonRegistryBackend(namespace=namespace, port_factory=lambda: _SqlitePgPort(conn))


def test_postgres_backend_contract_matches_sqlite_registry():
    backend = _pg_backend()
    backend.register_unique("k", {"v": 1})
    with pytest.raises(ValueError, match="duplicate"):
        backend.register_unique("k", {"v": 2})
    assert backend.compare_and_replace("k", {"v": 9}, {"v": 3}) is False
    assert backend.compare_and_replace("k", {"v": 1}, {"v": 3}) is True
    backend.replace("a", [1])
    assert backend.items() == (("a", [1]), ("k", {"v": 3}))
    assert backend.maybe_get("missing") is None
    with pytest.raises(KeyError):
        backend.get("missing")


def test_order_store_runs_on_postgres_backend_with_event_spine():
    from contracts.order import Order

    store = OrderStore(backend=_pg_backend(), event_store=MemoryEventStore(), require_event_spine=True)
    order = store.create_order(Order(order_id="o1", tenant_id="t", business_id="b", order_kind="k",
                                     state_key="s", created_at_ms=1, updated_at_ms=1), specialization={})
    assert store.get_canonical_order(order_id="o1", tenant_id="t", business_id="b") == order
    done = store.transition_order(order_id="o1", tenant_id="t", business_id="b",
                                  lifecycle_status="fulfilled", occurred_at_ms=2)
    assert done.lifecycle_status is OrderLifecycleStatus.FULFILLED


def test_backend_selection_is_explicit_and_fails_closed(monkeypatch):
    monkeypatch.setenv("BUSINESAIOS_CLIENT_OUTCOME_BACKEND", "postgres")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    with pytest.raises(RuntimeError, match="requires POSTGRES_DSN"):
        ClientOutcomePersistenceOwner.default()
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://u@h/db")
    assert isinstance(ClientOutcomePersistenceOwner.default().registry("order"), PostgresJsonRegistryBackend)
    monkeypatch.setenv("BUSINESAIOS_CLIENT_OUTCOME_BACKEND", "mysql")
    with pytest.raises(RuntimeError, match="unsupported"):
        ClientOutcomePersistenceOwner.default()
