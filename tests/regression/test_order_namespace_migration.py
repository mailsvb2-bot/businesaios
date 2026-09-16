from __future__ import annotations

from datetime import UTC, datetime

from lead_outcomes.client_outcome_contract import ClientOutcomeOrder, ClientOutcomePackage
from lead_outcomes.client_outcome_order_store import ClientOutcomeOrderStore, OrderStore
from runtime.platform.client_outcome_persistence import ClientOutcomePersistenceOwner


def _configure(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "BUSINESAIOS_CLIENT_OUTCOME_DB_PATH",
        str(tmp_path / "client-outcome.sqlite3"),
    )
    monkeypatch.delenv("BUSINESAIOS_REPLICA_COUNT", raising=False)
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    monkeypatch.delenv("UVICORN_WORKERS", raising=False)


def _order() -> ClientOutcomeOrder:
    return ClientOutcomeOrder(
        order_id="legacy-sqlite-order",
        tenant_id="tenant-a",
        business_id="business-a",
        package=ClientOutcomePackage(
            package_id="clients-5",
            label="5 clients",
            requested_clients=5,
            price_per_verified_client=50.0,
        ),
        created_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )


def _legacy_payload(order: ClientOutcomeOrder) -> dict[str, object]:
    return {
        "order_id": order.order_id,
        "tenant_id": order.tenant_id,
        "business_id": order.business_id,
        "package": OrderStore._package_payload(order.package),
        "created_at": order.created_at.isoformat(),
        "metadata": {},
    }


def test_sqlite_legacy_order_migrates_to_canonical_namespace_and_survives_rebuild(
    monkeypatch,
    tmp_path,
) -> None:
    _configure(monkeypatch, tmp_path)
    persistence = ClientOutcomePersistenceOwner.default()
    legacy = persistence.registry("client_outcome_order")
    order = _order()
    legacy.replace(order.order_id, _legacy_payload(order))

    first = ClientOutcomeOrderStore(
        backend=persistence.registry("order"),
        legacy_backend=legacy,
    )
    assert first.get_order(order.order_id) == order
    assert persistence.registry("order").maybe_get(order.order_id) is not None

    rebuilt_persistence = ClientOutcomePersistenceOwner.default()
    rebuilt = ClientOutcomeOrderStore(
        backend=rebuilt_persistence.registry("order"),
        legacy_backend=rebuilt_persistence.registry("client_outcome_order"),
    )
    assert rebuilt.get_order(order.order_id) == order
