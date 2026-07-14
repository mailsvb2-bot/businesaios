from __future__ import annotations

import inspect

import pytest

from runtime.platform.event_store.postgres_event_store import (
    PostgresEventStore,
    _where_clause,
)
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
from runtime.platform.event_store.sqlite_event_store_query_api import (
    SqliteEventStoreQueryApi,
)


@pytest.mark.lock
def test_sqlite_and_postgres_latest_read_surfaces_accept_event_types() -> None:
    for owner in (SqliteEventStoreQueryApi, PostgresEventStore):
        assert "event_types" in inspect.signature(owner.latest_event).parameters
        assert "event_types" in inspect.signature(owner.latest_events).parameters


@pytest.mark.lock
def test_sqlite_and_postgres_iter_events_accept_canonical_event_types_filter() -> None:
    for owner in (SqliteEventStoreQueryApi, PostgresEventStore):
        signature = inspect.signature(owner.iter_events)
        assert "event_types" in signature.parameters
        assert "limit" in signature.parameters


@pytest.mark.lock
def test_postgres_multi_type_where_clause_keeps_all_requested_event_types() -> None:
    where, params = _where_clause(
        tenant_id="business-a",
        start_ms=0,
        end_ms=None,
        user_id="user-1",
        event_type=None,
        event_types=(
            "payment_created",
            "payment_succeeded",
            "payment_failed",
            "payment_captured",
        ),
    )

    assert "event_type IN (%s,%s,%s,%s)" in where
    assert params == (
        "business-a",
        0,
        "user-1",
        "payment_created",
        "payment_succeeded",
        "payment_failed",
        "payment_captured",
    )


@pytest.mark.lock
def test_sqlite_multi_type_iteration_returns_all_requested_types(tmp_path) -> None:
    path = tmp_path / "events.db"
    with SqliteEventStore(str(path)) as store:
        for index, event_type in enumerate(
            (
                "payment_created",
                "payment_succeeded",
                "unrelated_event",
            ),
            1,
        ):
            store.append_event(
                {
                    "event_id": f"event-{index}",
                    "tenant_id": "business-a",
                    "user_id": "user-1",
                    "source": "test",
                    "event_type": event_type,
                    "timestamp_ms": index,
                    "decision_id": "decision-1",
                    "correlation_id": "correlation-1",
                    "payload": {},
                }
            )

        rows = list(
            store.iter_events(
                tenant_id="business-a",
                start_ms=0,
                event_types=("payment_created", "payment_succeeded"),
                limit=10,
            )
        )

    assert [row["event_type"] for row in rows] == [
        "payment_created",
        "payment_succeeded",
    ]
