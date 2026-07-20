from __future__ import annotations

import pytest

from contracts.platforms.market_intelligence_advanced_contract import ProviderCursor
from runtime._internal.market_intelligence.http_transport import HttpRequest, HttpResponse
from runtime._internal.market_intelligence.pagination import PageCursor
from runtime._internal.market_intelligence.provider_clients import (
    MarketIntelligenceProviderClient,
    ProviderPlanRegistry,
    ProviderRequestPlan,
    _text,
)
from runtime._internal.market_intelligence.provider_runtime import (
    ProviderRequestPlanV2,
    ProviderRuntimeError,
)
from runtime._internal.market_intelligence.recovery import RecoveryVerdict
from runtime._internal.market_intelligence.state_store import SyncCheckpoint


class CursorStore:
    def __init__(self, cursor=None):
        self.cursor = cursor or ProviderCursor("tenant-a", "provider-a", "family", "global")
        self.saved = []

    def load(self, **kwargs):
        return self.cursor

    def save(self, cursor):
        self.saved.append(cursor)
        self.cursor = cursor
        return cursor


class StateStore:
    def __init__(self, checkpoint=None):
        self.checkpoint = checkpoint or SyncCheckpoint("tenant-a", "provider-a", "family", "global", "old", "old-time", "old-sum", 1, {})
        self.begun = []
        self.finished = []
        self.saved = []

    def load_checkpoint(self, **kwargs):
        return self.checkpoint

    def begin_run(self, **kwargs):
        self.begun.append(kwargs)

    def finish_run(self, **kwargs):
        self.finished.append(kwargs)

    def save_checkpoint(self, checkpoint):
        self.saved.append(checkpoint)
        self.checkpoint = checkpoint
        return checkpoint


class Recovery:
    def __init__(self, verdict=None, state_store=None):
        self.verdict = verdict or RecoveryVerdict(True, "ok", "replay-key", "resume", False, False)
        self.state_store = state_store
        self.quarantined = []

    def preflight(self, **kwargs):
        return self.verdict

    def quarantine_poisoned_source(self, **kwargs):
        self.quarantined.append(kwargs)


class Transport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, provider, request):
        self.calls.append((provider, request))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RuntimeFactory:
    def __init__(self, plan=None, rows=None, error=None):
        self.plan = plan
        self.rows = rows
        self.error = error
        self.build_calls = []
        self.map_calls = []

    def build_plan(self, **kwargs):
        self.build_calls.append(kwargs)
        if self.error:
            raise self.error
        return self.plan

    def normalize_records(self, **kwargs):
        if isinstance(self.rows, Exception):
            raise self.rows
        return list(self.rows if self.rows is not None else kwargs["records"])

    def map_transport_error(self, *, provider, exc):
        self.map_calls.append((provider, exc))
        return ProviderRuntimeError("transport_error", f"mapped:{exc}", provider=provider)


def legacy_plan(**overrides):
    values = dict(
        provider="provider-a",
        source_family="family",
        operation="search",
        url="https://api.example/search",
        params={"fixed": "1"},
        page_size=2,
        max_pages=2,
    )
    values.update(overrides)
    return ProviderRequestPlan(**values)


def runtime_plan(**overrides):
    values = dict(
        provider="provider-a",
        source_family="family",
        operation="search",
        request=HttpRequest("GET", "https://api.example/search", params={"fixed": "1"}),
        item_path="items",
        next_cursor_path="next",
        page_size_param="limit",
        cursor_param="cursor",
        max_pages=2,
        version="v1",
        manifest={"provider": "provider-a"},
    )
    values.update(overrides)
    return ProviderRequestPlanV2(**values)


def response(payload, status=200):
    return HttpResponse(status_code=status, headers={}, text="", json_payload=payload)


def client(*, transport=None, cursor_store=None, registry=None, runtime_factory=None, state_store=None, recovery=None):
    state = state_store or StateStore()
    rec = recovery or Recovery(state_store=state)
    return MarketIntelligenceProviderClient(
        transport=transport or Transport(),
        cursor_store=cursor_store or CursorStore(),
        plan_registry=registry or ProviderPlanRegistry(),
        runtime_factory=runtime_factory or RuntimeFactory(plan=runtime_plan()),
        state_store=state,
        recovery=rec,
    )


def test_registry_and_client_wiring():
    registry = ProviderPlanRegistry()
    assert not registry.has(provider="p", source_family="f", operation="o")
    with pytest.raises(KeyError, match="unknown provider plan"):
        registry.resolve(provider="p", source_family="f", operation="o", payload={})
    registry.register(provider="p", source_family="f", operation="o", builder=lambda payload: legacy_plan(params=payload))
    assert registry.has(provider="p", source_family="f", operation="o")
    assert registry.resolve(provider="p", source_family="f", operation="o", payload={"x": 1}).params == {"x": 1}

    state = StateStore()
    rec = Recovery(state_store=object())
    wired = client(state_store=state, recovery=rec)
    assert wired.recovery.state_store is state
    same = Recovery(state_store=state)
    assert client(state_store=state, recovery=same).recovery.state_store is state
    assert _text(None, default="d") == "d"


def test_legacy_dry_run_and_execute_two_pages():
    registry = ProviderPlanRegistry()
    registry.register(provider="provider-a", source_family="family", operation="search", builder=lambda payload: legacy_plan())
    cursor_store = CursorStore(ProviderCursor("tenant-a", "provider-a", "family", "q", cursor="before", last_seen_at="before-time", checksum="before-sum"))
    dry = client(cursor_store=cursor_store, registry=registry)
    result = dry.execute_market_intelligence(
        provider="provider-a",
        source_family="family",
        operation="search",
        payload={"tenant_id": "tenant-a", "query": "q", "limit": "bad", "page_limit": 0},
        dry_run=True,
    )
    assert result["code"] == "dry_run" and result["plan"]["page_limit"] == 2

    transport = Transport(
        response({"items": [{"id": "1", "updated_at": "t1"}], "next_cursor": "c2"}),
        response({"items": [{"id": "2", "published_at": "t2"}], "next_cursor": None}),
    )
    executed = client(transport=transport, cursor_store=cursor_store, registry=registry)
    out = executed.execute_market_intelligence(
        provider="provider-a",
        source_family="family",
        operation="search",
        payload={"tenant_id": "tenant-a", "query": "q", "limit": 5, "page_limit": 1},
        dry_run=False,
    )
    assert out["code"] == "executed" and len(out["records"]) == 2
    assert cursor_store.saved[-1].cursor == "c2"
    assert transport.calls[1][1].params["cursor"] == "c2"


def test_enterprise_quarantine_and_replay():
    blocked = Recovery(RecoveryVerdict(False, "blocked", "key", None, True, False))
    with pytest.raises(ProviderRuntimeError, match="quarantined"):
        client(recovery=blocked).execute_market_intelligence(
            provider="provider-a", source_family="family", operation="search", payload={}, dry_run=False
        )

    state = StateStore()
    replay = Recovery(RecoveryVerdict(True, "ok", "key", "resume", False, True), state_store=state)
    out = client(state_store=state, recovery=replay).execute_market_intelligence(
        provider="provider-a", source_family="family", operation="search", payload={}, dry_run=False
    )
    assert out["code"] == "replay_hit" and out["cursor"] == "old"
    assert not state.begun


def test_enterprise_dry_run_finishes_journal():
    state = StateStore()
    out = client(state_store=state).execute_market_intelligence(
        provider="provider-a",
        source_family="family",
        operation="search",
        payload={"tenant_id": "tenant-a", "query": "q"},
        dry_run=True,
    )
    assert out["code"] == "dry_run"
    assert state.begun and state.finished[-1]["status"] == "dry_run"
    assert state.finished[-1]["checkpoint_after"] is state.checkpoint


def test_enterprise_success_checkpoint_and_fallback_tokens():
    plan = runtime_plan()
    transport = Transport(
        response({"items": [{"id": "1", "updated_at": "t1"}], "next": "c2"}),
        response({"items": [{"id": "2", "published_at": "t2"}], "next": None}),
    )
    state = StateStore()
    runtime = RuntimeFactory(plan=plan, rows=[
        {"external_id": "1", "updated_at": "t1"},
        {"external_id": "2", "published_at": "t2"},
    ])
    out = client(transport=transport, runtime_factory=runtime, state_store=state).execute_market_intelligence(
        provider="provider-a",
        source_family="family",
        operation="search",
        payload={"tenant_id": "tenant-a", "query": "q", "limit": 10, "page_size": 1},
        dry_run=False,
    )
    assert out["code"] == "executed" and out["cursor"] == "c2"
    assert state.finished[-1]["status"] == "succeeded"
    assert state.saved[-1].last_seen_at == "t2"
    assert out["page_metadata"][-1]["next_cursor_token"] is None


def test_enterprise_plan_failure_is_finalized_and_mapped():
    state = StateStore()
    runtime = RuntimeFactory(error=ValueError("bad plan"))
    with pytest.raises(ProviderRuntimeError, match="mapped:bad plan") as caught:
        client(runtime_factory=runtime, state_store=state).execute_market_intelligence(
            provider="provider-a", source_family="family", operation="search", payload={}, dry_run=False
        )
    assert caught.value.code == "transport_error"
    assert state.finished[-1]["status"] == "failed"
    assert state.finished[-1]["error_code"] == "transport_error"


def test_enterprise_provider_error_quarantines_and_preserves_identity():
    state = StateStore()
    rec = Recovery(state_store=state)
    err = ProviderRuntimeError("contract_violation", "poison", provider="provider-a", details={"field": "x"})
    runtime = RuntimeFactory(plan=runtime_plan(), rows=err)
    with pytest.raises(ProviderRuntimeError) as caught:
        client(runtime_factory=runtime, state_store=state, recovery=rec, transport=Transport(response({"items": [], "next": None}))).execute_market_intelligence(
            provider="provider-a", source_family="family", operation="search", payload={}, dry_run=False
        )
    assert caught.value is err
    assert rec.quarantined[-1]["reason_code"] == "contract_violation"
    assert state.finished[-1]["poisoned"] is True


def test_fetch_extract_scope_fingerprint_and_helpers():
    transport = Transport(response([{"id": "1"}]), response({"nested": {"items": [{"id": "2"}], "next": "n"}}))
    c = client(transport=transport)
    legacy = legacy_plan(item_path="$", next_cursor_path="missing")
    page = c._fetch_page(plan=legacy, payload={"timeout_seconds": 3}, cursor=None, requested_page_limit=2)
    assert page.items == ({"id": "1"},) and page.exhausted

    runtime = runtime_plan(item_path="nested.items", next_cursor_path="nested.next")
    page2 = c._fetch_page_runtime(plan=runtime, payload={}, cursor=PageCursor("old", 3), page_limit=2)
    assert page2.next_cursor == PageCursor("n", 4)
    assert transport.calls[-1][1].params["cursor"] == "old"

    assert c._extract_items({"a": {"b": [1]}}, "a.b") == [1]
    assert c._extract_items({"a": [2]}, "$.a") == [2]
    assert c._extract_items({"a": 1}, "a.b") == []
    assert c._extract_scalar({"a": {"b": " x "}}, "a.b") == "x"
    assert c._extract_scalar({"a": " y "}, "$.a") == "y"
    assert c._extract_scalar({"a": 1}, "a.b") is None
    assert c._extract_scalar(" root ", "$") == "root"
    assert c._scope_key({}) == "global"
    assert len(c._scope_key({"query": "x" * 200})) == 64
    assert c._scope_key({"query": "q", "region": "eu"}) == "q|eu"
    assert c._request_fingerprint({1: "a", "x": "b", "risk": 1, "idempotency_key": "secret"}) == c._request_fingerprint({"x": "b", 1: "a"})
    assert c._last_record_token(()) is None
    assert c._last_record_token(({"record_id": "r"},)) == "r"
    assert c._last_seen_at(()) is None
    assert c._last_seen_at(({"observed_at": "t"},)) == "t"
    assert c._checksum(()) == c._checksum(())
    assert c._bounded_int("bad", default=7, upper=10) == 7
    assert c._bounded_int(99, default=7, upper=10) == 10
