from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from execution.market_intelligence_loop import (
    MarketIntelligenceExecutionError,
    MarketIntelligenceLoop,
)
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest


class Policy:
    def validate_request(self, request):
        return request

    def summarize_result(self, result):
        return {"records_count": len(result.get("records") or [])}


class Governance:
    def enforce(self, request, *, tenancy_scope=None):
        return request, {
            "risk_level": "low" if tenancy_scope is None else "scoped",
            "requires_approval": bool(tenancy_scope),
        }


class Compliance:
    def __init__(self, *, fail=False):
        self.fail = fail

    def enforce_pre_ingestion(self, *, provider, payload):
        if self.fail:
            raise ValueError("compliance blocked")
        return {**payload, "compliance": {"provider": provider, "allowed": True}}


class Economic:
    def __init__(self):
        self.allowed = []
        self.usage = []

    def ensure_allowed(self, **kwargs):
        self.allowed.append(kwargs)

    def record_usage(self, **kwargs):
        self.usage.append(kwargs)


class Operator:
    def __init__(self, *, fail_check=False):
        self.fail_check = fail_check
        self.checked = []
        self.reviews = []
        self.escalations = []

    def check_source_allowed(self, **kwargs):
        self.checked.append(kwargs)
        if self.fail_check:
            raise ValueError("source banned")

    def enqueue_review(self, **kwargs):
        review_id = f"review:{len(self.reviews) + 1}"
        self.reviews.append((review_id, kwargs))
        return review_id

    def escalate_review(self, **kwargs):
        self.escalations.append(kwargs)

    def snapshot(self):
        return {"reviews": len(self.reviews), "escalations": len(self.escalations)}


class Quota:
    def __init__(self):
        self.consumed = []

    def consume(self, request):
        self.consumed.append(request)

    def snapshot(self):
        return {"consumed": len(self.consumed)}


class Retry:
    def __init__(self, retryable=("provider_error", "timeout", "provider_contract_error"), max_attempts=2):
        self.retryable = set(retryable)
        self.max_attempts = max_attempts

    def should_retry(self, *, code, attempt):
        return code in self.retryable and attempt < self.max_attempts

    def backoff_seconds(self, attempt):
        return 0.0


class Circuit:
    def __init__(self):
        self.success = []
        self.failure = []
        self.ensured = []

    def ensure_open(self, provider):
        self.ensured.append(provider)

    def on_success(self, provider):
        self.success.append(provider)

    def on_failure(self, provider):
        self.failure.append(provider)

    def snapshot(self):
        return {"success": len(self.success), "failure": len(self.failure)}


class Idempotency:
    def __init__(self, initial=None, *, fail_put=False):
        self.values = dict(initial or {})
        self.puts = []
        self.fail_put = fail_put

    def get(self, key):
        value = self.values.get(key)
        return dict(value) if value is not None else None

    def put(self, key, value):
        if self.fail_put:
            raise RuntimeError("cache unavailable")
        self.puts.append((key, dict(value)))
        self.values[key] = dict(value)


class Normalizer:
    def __init__(self, *, fail=False):
        self.fail = fail

    def normalize_record(self, record):
        if self.fail:
            raise RuntimeError("normalization failed")
        return dict(record)


class Deduplicator:
    def deduplicate(self, records):
        seen = set()
        out = []
        for record in records:
            key = record.get("external_id")
            if key in seen:
                continue
            seen.add(key)
            out.append(record)
        return out


@dataclass
class Row:
    value: dict

    def as_dict(self):
        return dict(self.value)


class Dataset:
    def build_rows(self, result):
        return [Row({"record_id": item.get("external_id")}) for item in result.get("records") or []]


class WorldState:
    def to_world_state_patch(self, result):
        return {"records": len(result.get("records") or [])}


class Memory:
    def __init__(self, *, derived=False):
        self.derived = derived

    def to_memory_payload(self, result):
        payload = {"records": len(result.get("records") or [])}
        if self.derived:
            payload["derived_evidence"] = {
                "evidence_id": "e-1",
                "derived_kind": "trend",
                "policy_name": "policy-v1",
            }
        return payload


class Telemetry:
    def __init__(self):
        self.events = []
        self.traces = []

    def emit(self, name, **kwargs):
        self.events.append((name, kwargs))

    def start_trace(self, **kwargs):
        self.traces.append(("start", kwargs))

    def finish_trace(self, **kwargs):
        self.traces.append(("finish", kwargs))

    def emit_provenance_audit(self, **kwargs):
        self.events.append(("provenance", kwargs))

    def observe_latency(self, **kwargs):
        self.events.append(("latency", kwargs))

    def observe_dedup_effectiveness(self, **kwargs):
        self.events.append(("dedup", kwargs))

    def observe_source_quality(self, **kwargs):
        self.events.append(("quality", kwargs))

    def observe_error(self, **kwargs):
        self.events.append(("error", kwargs))

    def snapshot(self):
        return {"events": [name for name, _ in self.events]}


class Observability:
    def __init__(self):
        self.runs = []
        self.anomalies = []
        self.provenance = []

    def append_run(self, run):
        self.runs.append(run)

    def append_anomaly(self, **kwargs):
        self.anomalies.append(kwargs)

    def append_provenance(self, **kwargs):
        self.provenance.append(kwargs)

    def snapshot(self):
        return {
            "runs": len(self.runs),
            "anomalies": len(self.anomalies),
            "provenance": len(self.provenance),
        }


class Evaluation:
    def __init__(self, quality=0.8):
        self.quality = quality

    def provider_quality_score(self, *, records):
        return self.quality if records else 0.0

    def regression_summary(self, **kwargs):
        return {"regression": "ok", "provider_records": len(kwargs["provider_records"])}


def request(**changes):
    values = {
        "tenant_id": "tenant-a",
        "source_family": "marketplace",
        "provider": "amazon",
        "action_type": "sync_catalog",
        "query": "shoes",
    }
    values.update(changes)
    return MarketIntelligenceIngestionRequest(**values)


def make_loop(execute_action, *, quality=0.8, derived=False, cached=None, normalize_fail=False, retry=None, compliance=None, operator=None, fail_put=False):
    return MarketIntelligenceLoop(
        execute_action=execute_action,
        policy=Policy(),
        governance=Governance(),
        compliance=compliance or Compliance(),
        economic_control=Economic(),
        operator_control=operator or Operator(),
        quota_guard=Quota(),
        retry_policy=retry or Retry(),
        circuit_breaker=Circuit(),
        idempotency_store=Idempotency(cached, fail_put=fail_put),
        normalizer=Normalizer(fail=normalize_fail),
        deduplicator=Deduplicator(),
        dataset_builder=Dataset(),
        world_state_adapter=WorldState(),
        memory_bridge=Memory(derived=derived),
        telemetry=Telemetry(),
        observability_store=Observability(),
        evaluation=Evaluation(quality),
    )


def test_execution_error_normalizes_code_and_message():
    error = MarketIntelligenceExecutionError("  TIMEOUT  ", "  later  ")
    assert error.code == "timeout"
    assert str(error) == "later"
    fallback = MarketIntelligenceExecutionError("", "")
    assert fallback.code == "provider_error"
    assert str(fallback) == "provider_error"


def test_cached_result_refreshes_all_runtime_snapshots(monkeypatch):
    probe = make_loop(lambda *_: pytest.fail("provider must not run"))
    key = __import__("execution.market_intelligence_idempotency", fromlist=["build_market_intelligence_idempotency_key"]).build_market_intelligence_idempotency_key(request())
    probe.idempotency_store.values[key] = {"ok": True, "records": []}
    result = probe.run(request())
    assert result["idempotency_hit"] is True
    assert "market_intelligence_idempotency_hit" in result["telemetry_snapshot"]["events"]
    assert result["observability_snapshot"] == {"runs": 0, "anomalies": 0, "provenance": 0}
    assert probe.quota_guard.consumed == []


def test_success_derived_evidence_dedup_and_low_quality_review(monkeypatch):
    monkeypatch.setattr("execution.market_intelligence_loop.time.sleep", lambda _: None)
    loop = make_loop(
        lambda *_: {
            "ok": True,
            "executed": True,
            "records": [
                {"external_id": "1", "title": "One"},
                {"external_id": "1", "title": "Duplicate"},
                "ignored",
            ],
        },
        quality=0.2,
        derived=True,
    )
    result = loop.run(request(), tenancy_scope=SimpleNamespace())
    assert [item["external_id"] for item in result["records"]] == ["1"]
    assert result["governance"]["requires_approval"] is True
    assert result["derived_evidence"]["evidence_id"] == "e-1"
    assert result["dataset_rows"] == [{"record_id": "1"}]
    assert result["world_state_patch"] == {"records": 1}
    assert loop.operator_control.reviews[0][1]["reason"] == "low_quality_result"
    assert loop.observability_store.provenance
    assert loop.idempotency_store.puts


def test_empty_result_is_escalated_and_global_scope_used():
    loop = make_loop(lambda *_: {"records": None})
    req = request(query=None, subject_url=None, account_ref=None)
    result = loop.run(req)
    assert result["records"] == []
    assert loop.operator_control.reviews[0][1]["reason"] == "empty_result"
    assert loop.operator_control.escalations[0]["reason"] == "empty_result"
    assert loop.observability_store.runs[0].metadata["scope_key"] == "global"


def test_explicit_provider_error_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("execution.market_intelligence_loop.time.sleep", lambda _: None)
    calls = []

    def execute(*_):
        calls.append(1)
        if len(calls) == 1:
            return {"ok": False, "code": "TIMEOUT", "message": "later"}
        return {"executed": True, "records": ({"external_id": "2"},)}

    loop = make_loop(execute)
    result = loop.run(request(subject_url="https://example.test", query=None))
    assert result["records"][0]["external_id"] == "2"
    assert len(calls) == 2
    assert any(name == "market_intelligence_retry_scheduled" for name, _ in loop.telemetry.events)


def test_executed_false_fails_without_retry():
    loop = make_loop(
        lambda *_: {"executed": False, "code": "rejected", "message": "no"},
        retry=Retry(retryable=()),
    )
    with pytest.raises(MarketIntelligenceExecutionError, match="no") as caught:
        loop.run(request(account_ref="acct", query=None))
    assert caught.value.code == "rejected"
    assert loop.circuit_breaker.failure == ["amazon"]
    assert loop.operator_control.escalations[0]["reason"] == "rejected"
    assert loop.observability_store.runs[0].status == "failed"


def test_generic_provider_exception_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("execution.market_intelligence_loop.time.sleep", lambda _: None)
    calls = []

    def execute(*_):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("network")
        return {"records": [{"external_id": "3"}]}

    loop = make_loop(execute)
    assert loop.run(request())["records"][0]["external_id"] == "3"
    assert len(calls) == 2


def test_post_provider_failure_does_not_reexecute_or_cache(monkeypatch):
    monkeypatch.setattr("execution.market_intelligence_loop.time.sleep", lambda _: None)
    calls = []

    def execute(*_):
        calls.append(1)
        return {"records": [{"external_id": "4"}]}

    loop = make_loop(execute, normalize_fail=True, retry=Retry(max_attempts=5))
    with pytest.raises(MarketIntelligenceExecutionError, match="normalization failed"):
        loop.run(request())
    assert len(calls) == 1
    assert loop.idempotency_store.puts == []
    assert loop.observability_store.runs[0].status == "failed"


def test_cache_write_failure_does_not_reexecute_provider(monkeypatch):
    monkeypatch.setattr("execution.market_intelligence_loop.time.sleep", lambda _: None)
    calls = []

    def execute(*_):
        calls.append(1)
        return {"records": [{"external_id": "5"}]}

    loop = make_loop(execute, fail_put=True, retry=Retry(max_attempts=5))
    with pytest.raises(MarketIntelligenceExecutionError, match="cache unavailable"):
        loop.run(request())
    assert len(calls) == 1


def test_preflight_rejections_do_not_consume_quota():
    compliance_loop = make_loop(lambda *_: {}, compliance=Compliance(fail=True))
    with pytest.raises(ValueError, match="compliance blocked"):
        compliance_loop.run(request())
    assert compliance_loop.quota_guard.consumed == []

    operator_loop = make_loop(lambda *_: {}, operator=Operator(fail_check=True))
    with pytest.raises(ValueError, match="source banned"):
        operator_loop.run(request())
    assert operator_loop.quota_guard.consumed == []


def test_result_normalization_and_scope_helpers():
    assert MarketIntelligenceLoop._normalize_result_payload({})["records"] == []
    assert MarketIntelligenceLoop._normalize_result_payload({"records": (1, 2)})["records"] == [1, 2]
    assert MarketIntelligenceLoop._normalize_result_payload({"records": []})["records"] == []
    with pytest.raises(MarketIntelligenceExecutionError, match="mapping"):
        MarketIntelligenceLoop._normalize_result_payload([])  # type: ignore[arg-type]
    with pytest.raises(MarketIntelligenceExecutionError, match="list or tuple"):
        MarketIntelligenceLoop._normalize_result_payload({"records": "bad"})

    assert MarketIntelligenceLoop._scope_key({"subject_url": " x ", "query": "q"}) == "x"
    assert MarketIntelligenceLoop._scope_key({"query": " q ", "account_ref": "a"}) == "q"
    assert MarketIntelligenceLoop._scope_key({"account_ref": " a "}) == "a"
    assert MarketIntelligenceLoop._scope_key({}) == "global"
