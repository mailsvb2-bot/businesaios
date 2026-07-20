from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from entrypoints.api.queue_ops_route_handlers import QueueOpsRouteHandlers
from entrypoints.api.queue_ops_route_support import (
    ROUTE_METADATA_MAX_ITEMS,
    ROUTE_METADATA_MAX_STRING,
    _age_seconds,
    alert_dict,
    build_consistency_snapshot,
    build_data_freshness,
    build_evidence_timeline,
    build_operator_summary,
    build_timeline_rows,
    normalize_hook_code,
    normalize_limit,
    normalize_optional,
    normalize_queue_name,
    normalize_source,
    sanitize_hook_item,
    sanitize_metadata,
    sanitize_value,
    slo_dict,
)
from runtime.queue.queue_operational_contracts import QueueAlert

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def slo(*, status="ok", reasons=()):
    return SimpleNamespace(
        tenant_id="tenant-a",
        queue_name="jobs",
        ok=status in {"ok", "healthy"},
        status=status,
        reasons=tuple(reasons),
        pending_jobs=3,
        active_claims=2,
        dead_letter_jobs=1,
        janitor_stale_seconds=None,
        leader_stale_seconds=5,
    )


def alert(code="a", severity="warning", *, created_at=NOW, tenant_id="tenant-a", queue_name="jobs"):
    return QueueAlert(
        tenant_id=tenant_id,
        queue_name=queue_name,
        code=code,
        severity=severity,
        message=f"message-{code}",
        created_at=created_at,
    )


def monitor(*, status="ok", alerts=(), sampled_at=NOW, delivery=None, backpressure=None):
    return SimpleNamespace(
        slo=slo(status=status),
        alerts=tuple(alerts),
        sampled_at=sampled_at,
        alert_delivery=delivery,
        backpressure=backpressure,
    )


@dataclass
class PlanEntry:
    generated_at: datetime = NOW
    hooks: tuple = ()


@dataclass
class ExecutionEntry:
    hook_code: str = "refresh"
    executed: bool = True
    reason: str = "done"
    executed_at: datetime = NOW
    category: str = "verification"
    metadata: object = None


@dataclass
class RouteEntry:
    action: str = "view"
    source: str = "control_plane"
    actor_id: str | None = "operator"
    request_id: str | None = "request"
    status: str = "ok"
    metadata: object = None
    recorded_at: datetime = NOW


class AuditStore:
    def __init__(self, plans=(), executions=()):
        self.plans = tuple(plans)
        self.executions = tuple(executions)
        self.calls = []

    def list_plan_entries(self, **kwargs):
        self.calls.append(("plans", kwargs))
        return self.plans[: kwargs["limit"]]

    def list_execution_entries(self, **kwargs):
        self.calls.append(("executions", kwargs))
        return self.executions[: kwargs["limit"]]


class HistoryStore:
    def __init__(self, entries=()):
        self.entries = tuple(entries)
        self.calls = []
        self.recorded = []

    def list_entries(self, **kwargs):
        self.calls.append(kwargs)
        return self.entries[: kwargs["limit"]]

    def record(self, **kwargs):
        self.recorded.append(kwargs)
        return kwargs


class RollupStore:
    def __init__(self, summary=None, windows=()):
        self.summary = summary
        self.windows = tuple(windows)
        self.calls = []

    def summarize(self, **kwargs):
        self.calls.append(("summary", kwargs))
        return self.summary

    def list_window_summaries(self, **kwargs):
        self.calls.append(("windows", kwargs))
        return self.windows


class Analytics:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def summarize(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class Health:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def sample(self, **kwargs):
        self.calls.append(kwargs)
        return self.report


class Remediation:
    def __init__(self, plan, report=None):
        self.plan_value = plan
        self.report = report
        self.plan_calls = []
        self.execute_calls = []

    def plan(self, **kwargs):
        self.plan_calls.append(kwargs)
        return self.plan_value

    def execute(self, **kwargs):
        self.execute_calls.append(kwargs)
        return self.report


class Sink:
    def __init__(self, values=(), *, callable_snapshot=True):
        self.values = tuple(values)
        if not callable_snapshot:
            self.snapshot = "not-callable"

    def snapshot(self):
        return self.values


class FalseyStore:
    def __bool__(self):
        return False


def make_handler(*, report=None, plan=None, analytics=None, audit=None, history=None, rollup=None, sink=None, execution_report=None):
    handler = object.__new__(QueueOpsRouteHandlers)
    object.__setattr__(handler, "store", object())
    object.__setattr__(handler, "observability", object())
    object.__setattr__(handler, "alert_sink", sink or Sink())
    object.__setattr__(handler, "rollup_store", rollup)
    object.__setattr__(handler, "remediation_audit_store", audit)
    object.__setattr__(handler, "remediation_route_history_store", history)
    object.__setattr__(handler, "health_monitor", Health(report or monitor()))
    default_plan = plan or SimpleNamespace(generated_at=NOW, hooks=())
    object.__setattr__(handler, "remediation", Remediation(default_plan, execution_report))
    default_analytics = analytics or SimpleNamespace(
        tenant_id="tenant-a",
        queue_name="jobs",
        plan_count=0,
        execution_count=0,
        route_event_count=0,
        most_used_hook_code=None,
        top_unexecuted_hook_code=None,
        execution_rate=0.0,
        source_counts={},
        status_counts={},
        hook_offer_counts={},
        reason_counts={},
        as_dict=lambda: {"execution_count": 0},
    )
    object.__setattr__(handler, "remediation_analytics", Analytics(default_analytics))
    return handler


def test_normalizers_and_limit_contracts():
    assert normalize_queue_name(" jobs ") == "jobs"
    assert normalize_source(None) == "control_plane"
    assert normalize_source(" api client ") == "api_client"
    assert normalize_hook_code(" refresh ") == "refresh"
    assert normalize_optional(None) is None
    assert normalize_optional(" ") is None
    assert normalize_optional(" x ") == "x"
    with pytest.raises(ValueError, match="queue_name"):
        normalize_queue_name(" ")
    with pytest.raises(ValueError, match="hook_code"):
        normalize_hook_code("")

    assert normalize_limit(5, default=20) == 5
    assert normalize_limit(0, default=20) == 20
    assert normalize_limit(-1, default=20) == 20
    assert normalize_limit(9999, default=20, upper=100) == 100
    assert normalize_limit(1, default=0, upper=0) == 1
    for value in (True, "bad", 1.5, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="integer"):
            normalize_limit(value, default=20)


def test_alert_slo_and_operator_summary_branches():
    item = alert("critical", "critical")
    assert alert_dict(item)["created_at"] == NOW.isoformat()
    report_dict = slo_dict(slo(status="degraded", reasons=("x",)))
    assert report_dict["reasons"] == ("x",)
    assert report_dict["leader_stale_seconds"] == 5

    analytics = SimpleNamespace(most_used_hook_code="h1", top_unexecuted_hook_code="h2", execution_rate=0.5)
    bare = build_operator_summary(
        monitor_report=monitor(alerts=(item,)),
        analytics_preview=analytics,
        audit_preview={},
        approval_preview={"approval_required_count": 1, "approval_required_hook_codes": ("h1",)},
        trend_preview={},
        data_freshness={},
        consistency={},
    )
    assert bare["critical_alert_count"] == 1
    assert bare["published_alert_count"] == 0
    assert bare["approval_required_hooks"] == ("h1",)

    delivery = SimpleNamespace(published=3, suppressed=2, had_suppression=True)
    verdict = SimpleNamespace(reason="pressure", starving_tenants=("t2",))
    full = build_operator_summary(
        monitor_report=monitor(delivery=delivery, backpressure=SimpleNamespace(global_verdict=verdict)),
        analytics_preview=analytics,
        audit_preview={"latest_route_action": "view", "latest_route_status": "ok", "execution_count": 2, "timeline_event_count": 4},
        approval_preview={"approval_required_hooks": ("legacy",)},
        trend_preview={"pending_direction": "up", "alert_churn": "down"},
        data_freshness={"state": "aging"},
        consistency={"state": "warning", "reasons": ("x",)},
    )
    assert full["published_alert_count"] == 3
    assert full["backpressure_reason"] == "pressure"
    assert full["starving_tenants"] == ("t2",)


def test_consistency_snapshot_all_states():
    analytics = SimpleNamespace(execution_count=0)
    ok = build_consistency_snapshot(
        monitor_report=monitor(status="degraded"),
        recent_alerts=(),
        approval_preview={},
        audit_preview={"timeline_event_count": 1, "execution_count": 0},
        analytics_preview=analytics,
        trend_preview={"pending_direction": "flat"},
        data_freshness={"state": "fresh"},
    )
    assert ok == {"state": "ok", "reasons": (), "issues": ()}

    warning = build_consistency_snapshot(
        monitor_report=monitor(status="ok"),
        recent_alerts=(alert(),),
        approval_preview={"approval_required_count": 1},
        audit_preview={"timeline_event_count": 0, "execution_count": 2},
        analytics_preview=SimpleNamespace(execution_count=2),
        trend_preview={"pending_direction": "up"},
        data_freshness={"state": "fresh"},
    )
    assert warning["state"] == "warning"
    assert "alerts_present_while_slo_ok" in warning["issues"]
    assert "pending_upward_pressure" in warning["issues"]

    degraded = build_consistency_snapshot(
        monitor_report=monitor(status="ok"),
        recent_alerts=(),
        approval_preview={},
        audit_preview={"timeline_event_count": 1, "execution_count": 1},
        analytics_preview=SimpleNamespace(execution_count=3),
        trend_preview={},
        data_freshness={"state": "stale"},
    )
    assert degraded["state"] == "degraded"
    assert degraded["reasons"] == ("stale_data", "analytics_audit_mismatch")


def test_evidence_and_audit_timelines_are_bounded_and_sorted():
    plan = SimpleNamespace(generated_at=NOW - timedelta(minutes=3), hooks=(1, 2))
    route = ({"kind": "route", "at": (NOW + timedelta(minutes=1)).isoformat(), "title": "latest"},)
    rows = build_evidence_timeline(
        monitor_report=monitor(sampled_at=NOW - timedelta(minutes=2)),
        recent_alerts=(alert(created_at=NOW - timedelta(minutes=1)),),
        remediation_plan=plan,
        approval_preview={"approval_required_count": 2},
        route_timeline=route,
        now=NOW,
        limit=99,
    )
    assert rows[0]["title"] == "latest"
    assert {row["entry_type"] for row in rows} >= {"health_sample", "alert", "remediation_plan", "approval_gate", "route"}

    without_sample = build_evidence_timeline(
        monitor_report=monitor(sampled_at=None),
        recent_alerts=(),
        remediation_plan=plan,
        approval_preview={},
        route_timeline=(),
        now=NOW,
        limit=1,
    )
    assert len(without_sample) == 1

    plans = (PlanEntry(generated_at=NOW - timedelta(minutes=5), hooks=(1,)),)
    executions = (ExecutionEntry(executed=False, metadata={"api_token": "secret"}),)
    routes = (RouteEntry(metadata={"nested": {"password": "p"}}),)
    timeline = build_timeline_rows(plans=plans, executions=executions, route_history=routes, limit=25)
    assert timeline[0]["entry_type"] in {"execution", "route_event"}
    execution = next(row for row in timeline if row["entry_type"] == "execution")
    assert execution["status"] == "review_required"
    assert execution["metadata"]["api_token"] == "[redacted]"
    route_row = next(row for row in timeline if row["entry_type"] == "route_event")
    assert route_row["metadata"]["nested"]["password"] == "[redacted]"


def test_freshness_handles_timezones_and_states():
    assert _age_seconds(now=NOW, observed_at=NOW - timedelta(seconds=10)) == 10
    naive = NOW.replace(tzinfo=None)
    assert _age_seconds(now=NOW, observed_at=naive - timedelta(seconds=5)) == 5
    assert _age_seconds(now=naive, observed_at=NOW + timedelta(seconds=5)) == 0

    fresh = build_data_freshness(monitor_report=SimpleNamespace(sampled_at="bad"), rollup_summary=None, now=NOW)
    assert fresh["state"] == "fresh"
    aging = build_data_freshness(
        monitor_report=SimpleNamespace(sampled_at=NOW - timedelta(seconds=350)),
        rollup_summary=SimpleNamespace(last_observed_at=NOW - timedelta(seconds=10)),
        now=NOW,
    )
    assert aging["state"] == "aging"
    stale = build_data_freshness(
        monitor_report=SimpleNamespace(sampled_at=NOW - timedelta(seconds=1)),
        rollup_summary=SimpleNamespace(last_observed_at=NOW - timedelta(seconds=901)),
        now=NOW,
    )
    assert stale["state"] == "stale"
    bad_rollup = build_data_freshness(
        monitor_report=SimpleNamespace(sampled_at=NOW),
        rollup_summary=SimpleNamespace(last_observed_at="bad"),
        now=NOW,
    )
    assert bad_rollup["last_rollup_at"] is None


def test_metadata_sanitization_is_fail_closed_and_json_safe():
    long = "x" * (ROUTE_METADATA_MAX_STRING + 10)
    payload = {
        "api_token": "secret",
        "nested": {"authorization": "bearer"},
        "items": list(range(ROUTE_METADATA_MAX_ITEMS + 2)),
        "set": {3, 1},
        "frozen": frozenset({"b", "a"}),
        "when": NOW,
        "long": long,
        "nan": float("nan"),
        "inf": float("inf"),
        "custom": SimpleNamespace(x=1),
    }
    sanitized = sanitize_metadata(payload)
    assert sanitized["api_token"] == "[redacted]"
    assert sanitized["nested"]["authorization"] == "[redacted]"
    assert sanitized["items"][-1] == "[truncated]"
    assert sanitized["set"] == (1, 3)
    assert sanitized["frozen"] == ("a", "b")
    assert sanitized["when"] == NOW.isoformat()
    assert sanitized["long"].endswith("...")
    assert sanitized["nan"] == "nan"
    assert sanitized["inf"] == "inf"
    assert "namespace" in sanitized["custom"].lower()
    assert sanitize_metadata(None) == {}
    with pytest.raises(ValueError, match="mapping"):
        sanitize_metadata([])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="collision"):
        sanitize_metadata({1: "a", "1": "b"})

    many = sanitize_metadata({f"k{i}": i for i in range(ROUTE_METADATA_MAX_ITEMS + 3)})
    assert many["__truncated__"] is True
    assert sanitize_value(None) is None
    assert sanitize_value(False) is False
    assert sanitize_value([1, 2]) == (1, 2)
    assert sanitize_value(set(range(ROUTE_METADATA_MAX_ITEMS + 2)))[-1] == "[truncated]"
    assert sanitize_hook_item({"code": "x", "metadata": {"session": "s"}})["metadata"]["session"] == "[redacted]"
    assert sanitize_hook_item({"code": "x"}) == {"code": "x"}
    assert sanitize_hook_item(object()).startswith("<object object")


def test_post_init_preserves_explicit_falsey_stores():
    rollup = FalseyStore()
    audit = FalseyStore()
    history = FalseyStore()
    handler = QueueOpsRouteHandlers(rollup_store=rollup, remediation_audit_store=audit, remediation_route_history_store=history)
    assert handler.rollup_store is rollup
    assert handler.remediation_audit_store is audit
    assert handler.remediation_route_history_store is history


def test_get_queue_ops_view_end_to_end_sanitizes_hook_metadata():
    hook = SimpleNamespace(
        code="refresh",
        label="Refresh",
        description="desc",
        severity="warning",
        operator_required=True,
        category="verification",
        runbook_hint=None,
        metadata={"secret": "value"},
    )
    plan = SimpleNamespace(generated_at=NOW, hooks=(hook,))
    rollup_summary = SimpleNamespace(
        samples=2,
        latest_status="ok",
        max_pending_jobs=3,
        max_active_claims=2,
        max_dead_letter_jobs=1,
        last_observed_at=None,
    )
    analytics_value = SimpleNamespace(
        tenant_id="tenant-a",
        queue_name="jobs",
        plan_count=1,
        execution_count=0,
        route_event_count=0,
        most_used_hook_code="refresh",
        top_unexecuted_hook_code="refresh",
        execution_rate=0.0,
        source_counts={"api": 1},
        status_counts={"ok": 1},
        hook_offer_counts={"refresh": 1},
        reason_counts={},
        as_dict=lambda: {"execution_count": 0},
    )
    audit = AuditStore(plans=(PlanEntry(hooks=({"metadata": {"password": "p"}},)),))
    history = HistoryStore(entries=(RouteEntry(metadata={"cookie": "c"}),))
    sink = Sink((alert("new", created_at=NOW), alert("other", tenant_id="tenant-b"), "bad"))
    handler = make_handler(
        report=monitor(alerts=(alert("new"),)),
        plan=plan,
        analytics=analytics_value,
        audit=audit,
        history=history,
        rollup=RollupStore(summary=rollup_summary),
        sink=sink,
    )
    result = handler.get_queue_ops_view(
        tenant_id="tenant-a",
        queue_name=" jobs ",
        actor_id=" operator ",
        request_id=" req ",
        source=" api client ",
        now=NOW,
    )
    assert result["queue_name"] == "jobs"
    assert result["alerts"][0]["code"] == "new"
    assert result["rollup_summary"]["last_observed_at"] is None
    assert result["remediation_plan"]["hooks"][0]["metadata"]["secret"] == "[redacted]"
    assert result["operator_summary"]["approval_required_hooks"] == ("refresh",)
    assert history.recorded[-1]["source"] == "api_client"
    assert history.recorded[-1]["metadata"]["request_id"] == "req"


def test_analytics_execute_and_audit_routes():
    analytics_value = SimpleNamespace(
        tenant_id="tenant-a",
        queue_name="jobs",
        execution_count=2,
        route_event_count=1,
        as_dict=lambda: {"execution_count": 2, "route_event_count": 1},
    )
    execution_report = SimpleNamespace(
        tenant_id="tenant-a",
        queue_name="jobs",
        hook_code="refresh",
        executed=True,
        reason="done",
        executed_at=NOW,
        category="verification",
    )
    audit = AuditStore(
        plans=(PlanEntry(hooks=({"metadata": {"api_key": "k"}},)),),
        executions=(ExecutionEntry(metadata={"password": "p"}),),
    )
    history = HistoryStore(entries=(RouteEntry(metadata={"token": "t"}),))
    handler = make_handler(analytics=analytics_value, audit=audit, history=history, execution_report=execution_report)

    analytics_result = handler.get_remediation_analytics(
        tenant_id="tenant-a", queue_name="jobs", limit=9999, actor_id="a", request_id="r", now=NOW
    )
    assert analytics_result["analytics"]["execution_count"] == 2
    assert handler.remediation_analytics.calls[0]["limit"] == 500

    executed = handler.execute_remediation_hook(
        tenant_id="tenant-a", queue_name="jobs", hook_code=" refresh ", actor_id="a", request_id="r", now=NOW
    )
    assert executed["executed"] is True
    assert executed["route_recorded"] is True
    assert history.recorded[-1]["status"] == "executed"

    audit_result = handler.list_remediation_audit(
        tenant_id="tenant-a",
        queue_name="jobs",
        limit=9999,
        timeline_limit=9999,
        action=" view ",
        status=" ok ",
        source_filter=" api ",
        now=NOW,
    )
    assert audit.calls[0][1]["limit"] == 500
    assert history.calls[0]["action"] == "view"
    assert audit_result["plans"][0]["hooks"][0]["metadata"]["api_key"] == "[redacted]"
    assert audit_result["executions"][0]["metadata"]["password"] == "[redacted]"
    assert audit_result["route_history"][0]["metadata"]["token"] == "[redacted]"
    assert len(audit_result["timeline"]) == 3


def test_handler_helpers_cover_empty_and_present_paths():
    empty = make_handler(audit=None, history=None, rollup=None, sink=Sink(callable_snapshot=False))
    assert empty._build_audit_preview(tenant_id="tenant-a", queue_name="jobs") == {
        "plan_count": 0,
        "execution_count": 0,
        "route_event_count": 0,
        "plan_preview_count": 0,
        "execution_preview_count": 0,
        "route_event_preview_count": 0,
        "timeline_event_count": 0,
        "preview_limited": True,
        "latest_plan_generated_at": None,
        "latest_execution_hook_code": None,
        "latest_execution_reason": None,
        "latest_route_action": None,
        "latest_route_status": None,
    }
    assert empty._build_timeline_preview(tenant_id="tenant-a", queue_name="jobs") == ()
    assert empty._build_trend_preview(tenant_id="tenant-a", queue_name="jobs", now=NOW)["pending_direction"] == "unknown"
    assert empty._recent_alerts(tenant_id="tenant-a", queue_name="jobs", limit=20) == ()
    empty._record_route_event(
        tenant_id="tenant-a", queue_name="jobs", action="view", source="api", status="ok", metadata={}, actor_id=None, request_id=None, now=NOW
    )

    hooks = (
        SimpleNamespace(operator_required=True, code="b", category="z"),
        SimpleNamespace(operator_required=True, code="a", category="a"),
        SimpleNamespace(operator_required=False, code="skip", category="x"),
        SimpleNamespace(),
    )
    approval = empty._build_approval_preview(plan=SimpleNamespace(hooks=hooks))
    assert approval["approval_required_count"] == 3
    assert approval["approval_required_hook_codes"] == ("b", "a")
    assert approval["review_categories"] == ("a", "z")

    wrapped_freshness = empty._build_data_freshness(monitor_report=monitor(), rollup_summary=None, now=NOW)
    assert wrapped_freshness["state"] == "fresh"
    wrapped_consistency = empty._build_consistency_snapshot(
        monitor_report=monitor(status="degraded"), recent_alerts=(), approval_preview={}, audit_preview={"timeline_event_count": 1}, analytics_preview=SimpleNamespace(execution_count=0), trend_preview={}, data_freshness={"state": "fresh"}
    )
    assert wrapped_consistency["state"] == "ok"


def test_trend_preview_all_directions_and_recent_alert_sorting():
    one = SimpleNamespace(
        max_pending_jobs=3,
        total_alert_count=2,
        total_critical_alert_count=1,
        latest_status="ok",
        window_start_at=NOW - timedelta(seconds=50),
    )
    handler = make_handler(rollup=RollupStore(windows=()))
    assert handler._build_trend_preview(tenant_id="tenant-a", queue_name="jobs", now=NOW)["window_count"] == 0

    object.__setattr__(handler, "rollup_store", RollupStore(windows=(one,)))
    single = handler._build_trend_preview(tenant_id="tenant-a", queue_name="jobs", now=NOW)
    assert single["pending_direction"] == "unknown"
    assert single["fresh_window_age_seconds"] == 50

    latest_up = SimpleNamespace(**{**one.__dict__, "max_pending_jobs": 5, "total_alert_count": 3})
    object.__setattr__(handler, "rollup_store", RollupStore(windows=(one, latest_up)))
    up = handler._build_trend_preview(tenant_id="tenant-a", queue_name="jobs", now=NOW)
    assert up["pending_direction"] == "up" and up["alert_churn"] == "up"

    latest_down = SimpleNamespace(**{**one.__dict__, "max_pending_jobs": 1, "total_alert_count": 1})
    object.__setattr__(handler, "rollup_store", RollupStore(windows=(one, latest_down)))
    down = handler._build_trend_preview(tenant_id="tenant-a", queue_name="jobs", now=NOW)
    assert down["pending_direction"] == "down" and down["alert_churn"] == "down"

    latest_flat = SimpleNamespace(**{**one.__dict__})
    delattr(latest_flat, "window_start_at")
    object.__setattr__(handler, "rollup_store", RollupStore(windows=(one, latest_flat)))
    flat = handler._build_trend_preview(tenant_id="tenant-a", queue_name="jobs", now=NOW)
    assert flat["pending_direction"] == "flat" and flat["alert_churn"] == "steady"
    assert flat["fresh_window_age_seconds"] is None

    object.__setattr__(handler, "alert_sink", Sink((
        alert("old", created_at=NOW - timedelta(seconds=10)),
        alert("new", created_at=NOW),
        alert("other", tenant_id="tenant-b"),
        "bad",
    )))
    recent = handler._recent_alerts(tenant_id="tenant-a", queue_name="jobs", limit=1)
    assert [item.code for item in recent] == ["new"]


def test_review_required_execution_and_missing_history():
    report = SimpleNamespace(
        tenant_id="tenant-a",
        queue_name="jobs",
        hook_code="inspect",
        executed=False,
        reason="operator_review_required",
        executed_at=NOW,
        category="inspection",
    )
    handler = make_handler(history=None, execution_report=report)
    result = handler.execute_remediation_hook(tenant_id="tenant-a", queue_name="jobs", hook_code="inspect", now=NOW)
    assert result["executed"] is False
    assert result["route_recorded"] is False
