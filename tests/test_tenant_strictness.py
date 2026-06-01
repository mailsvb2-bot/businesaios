from __future__ import annotations

import pytest


def test_contract_product_contract_requires_tenant_id():
    from contracts.product_contract import (
        EntitlementsSpec,
        EntryPolicy,
        ModuleSpec,
        ModulesSpec,
        Offer,
        OfferCatalog,
        ProductContract,
        TelemetryEventSpec,
        TelemetryField,
        TelemetrySchema,
    )

    pc = ProductContract(
        tenant_id="",
        product_id="organization_platform",
        domain="organization_platform",
        entry_policy=EntryPolicy(entrypoints=("telegram",), default_entrypoint="telegram"),
        offer_catalog=OfferCatalog(catalog_id="c1", offers=(Offer(offer_id="o1", title="t", price_minor=0, currency="RUB"),)),
        pricing_model=type("PM", (), {"pricing_model_id": "x", "choose_offer_id": lambda self, *, user_id, tenant_id, context: "o1"})(),
        telemetry_schema=TelemetrySchema(schema_id="s1", events=(TelemetryEventSpec("ui_click", (TelemetryField("key", "str"),)),)),
        entitlements=EntitlementsSpec(keys=("mt.access",)),
        modules=ModulesSpec(modules=(ModuleSpec(module_id="ring"),)),
    )
    with pytest.raises(ValueError):
        pc.validate()


def test_boot_request_requires_tenant_id():
    from runtime.boot.boot_context import BootRequest

    with pytest.raises(ValueError):
        BootRequest(tenant_id="", user_id="u", entrypoint="telegram", hints={}).self_check()


def test_event_log_requires_tenant_scope():
    from core.events.log import EventLog
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    with pytest.raises(ValueError):
        _ = EventLog(MemoryEventStore(), tenant="")

    elog = EventLog(MemoryEventStore(), tenant="t1")
    with pytest.raises(ValueError):
        # cross-tenant write blocked
        elog._append_event_dict({"tenant_id": "t2", "event_type": "x", "user_id": "u", "source": "s", "timestamp_ms": 0, "payload": {}})


def test_event_store_append_event_requires_tenant_id(tmp_path):
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    db = tmp_path / "events.sqlite"
    with SqliteEventStore(path=str(db)) as store:
        with pytest.raises(ValueError):
            store.append_event({"event_type": "x", "user_id": "u", "source": "s", "timestamp_ms": 0, "payload": {}})
