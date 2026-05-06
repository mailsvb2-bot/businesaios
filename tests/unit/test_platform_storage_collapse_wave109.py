from __future__ import annotations

import importlib


def test_event_store_contract_alias_routes_to_canonical_contract() -> None:
    legacy = importlib.import_module("runtime.platform.event_store.contract")
    canonical = importlib.import_module("contracts.event_store")
    assert legacy.EventStore is canonical.EventStore
    assert legacy.iter_events_strict is canonical.iter_events_strict


def test_runtime_serving_action_validator_alias_routes_to_final_owner() -> None:
    legacy = importlib.import_module("runtime.platform.support.serving.runtime.action_validator")
    canonical = importlib.import_module("application.decision.action_validator")
    assert legacy.ActionValidator is canonical.ActionValidator


def test_historical_event_store_split_imports_route_to_canonical_placeholder() -> None:
    mod = importlib.import_module("runtime.platform.event_store.postgres_event_store_part1")
    canonical = importlib.import_module("runtime.platform.event_store.postgres_event_store")
    assert mod is canonical
    meta = mod.describe_declared_absence()
    assert meta["placeholder"] is True
