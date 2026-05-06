from __future__ import annotations

import importlib


def test_postgres_split_alias_routes_to_canonical_placeholder() -> None:
    legacy = importlib.import_module("runtime.platform.event_store.postgres_event_store_part1")
    canonical = importlib.import_module("runtime.platform.event_store.postgres_event_store")
    assert legacy is canonical
    assert legacy.describe_declared_absence()["placeholder"] is True


def test_sqlite_split_alias_routes_to_canonical_read_queries() -> None:
    legacy = importlib.import_module("runtime.platform.event_store.sqlite_read_queries_part1")
    canonical = importlib.import_module("runtime.platform.event_store.sqlite_read_queries")
    assert legacy is canonical
    assert hasattr(legacy, "iter_events")
