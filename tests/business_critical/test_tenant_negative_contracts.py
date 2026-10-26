"""Negative tenant contracts: a missing/placeholder tenant is refused and tenants never see each other."""

from __future__ import annotations

import pytest

from application.business_autonomy.safety_core import validate_tenant_scope
from contracts.tenant_identity import require_tenant_id as strict_tenant_id
from core.tenancy import request_context as rc
from runtime.platform.event_store.memory_event_store import MemoryEventStore


@pytest.mark.parametrize("value", ["", "   ", None, "default", "legacy", "None", "null", " NULL "])
def test_strict_tenant_id_refuses_missing_and_placeholder_values(value) -> None:
    with pytest.raises(ValueError, match="tenant_id is required"):
        strict_tenant_id(value)


def test_strict_tenant_id_keeps_real_tenant() -> None:
    assert strict_tenant_id(" acme ") == "acme"


def test_request_context_without_binding_and_without_process_tenant_is_refused(monkeypatch) -> None:
    monkeypatch.delenv("TENANT_ID", raising=False)
    monkeypatch.setenv("RUN_MODE", "production")
    monkeypatch.setenv("ENV", "prod")
    assert rc.maybe_tenant_id() is None
    with pytest.raises((ValueError, rc.TenantRequired)):
        rc.require_tenant_id()


def test_request_context_refuses_blank_tenant_even_if_resolver_returns_it(monkeypatch) -> None:
    """Defence in depth: the guard itself must reject a blank tenant, not rely on as_tenant_id()."""
    monkeypatch.setattr(rc, "get_tenant_id", lambda: "  ")
    with pytest.raises(rc.TenantRequired, match="TENANT_REQUIRED"):
        rc.require_tenant_id()


def test_request_context_binding_is_scoped_and_restored(monkeypatch) -> None:
    monkeypatch.setenv("TENANT_ID", "process-tenant")
    with rc.tenant_scope("tenant-a"):
        assert rc.require_tenant_id() == "tenant-a"
        with rc.tenant_scope("tenant-b"):
            assert rc.require_tenant_id() == "tenant-b"
        assert rc.require_tenant_id() == "tenant-a"
    assert rc.maybe_tenant_id() is None
    assert rc.require_tenant_id() == "process-tenant"
    with pytest.raises(ValueError):
        rc.bind_tenant("   ")


_SCOPE_OK = {"tenant_id": "t1", "business_id": "b1", "binding_tenant_id": "t1"}


def test_safety_core_allows_matching_tenant_scope() -> None:
    assert validate_tenant_scope(**_SCOPE_OK).allowed is True


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"tenant_id": ""}, "tenant_id_required"),
        ({"tenant_id": "   "}, "tenant_id_required"),
        ({"tenant_id": "", "business_id": ""}, "tenant_id_required"),
        ({"tenant_id": "", "binding_tenant_id": ""}, "tenant_id_required"),
        ({"business_id": ""}, "business_id_required"),
        ({"binding_tenant_id": ""}, "tenant_binding_required"),
        ({"binding_tenant_id": "t2"}, "tenant_binding_mismatch"),
        ({"tenant_id": "global", "binding_tenant_id": "global"}, "global_tenant_forbidden"),
    ],
)
def test_safety_core_denies_with_the_specific_reason(override, reason) -> None:
    verdict = validate_tenant_scope(**{**_SCOPE_OK, **override})
    assert verdict.allowed is False
    assert verdict.reason == reason


def test_safety_core_global_tenant_only_with_explicit_fallback_flag() -> None:
    scope = {"tenant_id": "global", "business_id": "b1", "binding_tenant_id": "global"}
    assert validate_tenant_scope(**scope, allow_global_fallback=True).allowed is True


def test_event_store_isolates_two_tenants() -> None:
    store = MemoryEventStore()
    store.append_event({"tenant_id": "t1", "user_id": "u1", "event_type": "a", "timestamp_ms": 1})
    store.append_event({"tenant_id": "t2", "user_id": "u1", "event_type": "b", "timestamp_ms": 2})
    seen_t1 = [e["event_type"] for e in store.iter_events(tenant_id="t1")]
    seen_t2 = [e["event_type"] for e in store.iter_events(tenant_id="t2")]
    assert seen_t1 == ["a"] and seen_t2 == ["b"]
    assert list(store.iter_events(tenant_id="t3")) == []
    assert store.delete_user_events(tenant_id="t1", user_id="u1") == 1
    assert [e["event_type"] for e in store.iter_events(tenant_id="t2")] == ["b"]
