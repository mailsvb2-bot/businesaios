from __future__ import annotations

from types import SimpleNamespace

import pytest

from observability.inference_runtime_summary import (
    InferenceRuntimeSummaryService,
    _acceleration_batch_utilization_bucket,
    _safe_dict,
    _safe_float,
    _safe_text,
)


class _AuditLog:
    def __init__(self, records) -> None:
        self.records = list(records)
        self.calls: list[tuple[str, int]] = []

    def list_by_tenant(self, *, tenant_id: str, limit: int):
        self.calls.append((tenant_id, limit))
        return [row for row in self.records if row.get("tenant_id") == tenant_id]


class _EventLog:
    def __init__(self, events=()) -> None:
        self.events = tuple(events)

    def list_events(self):
        return self.events


class _StateStore:
    def get(self):
        return SimpleNamespace(active_tier=SimpleNamespace(value="standard"), frozen=False)


class _Health:
    def snapshots(self):
        return (
            SimpleNamespace(provider_name="p1", healthy=True, availability_score=0.9, latency_score=0.8, error_rate=0.1, saturation_score=0.2),
            SimpleNamespace(provider_name="p2", healthy=False, availability_score=0.4, latency_score=0.3, error_rate=0.5, saturation_score=0.8),
        )


def _service(*, records=(), burns=(), escalations=(), accelerations=None, with_audit=True):
    return InferenceRuntimeSummaryService(
        state_store=_StateStore(),
        provider_health_monitor=_Health(),
        escalation_audit_log=_EventLog(escalations),
        budget_burn_log=_EventLog(burns),
        action_audit_log=_AuditLog(records) if with_audit else None,
        acceleration_log=None if accelerations is None else _EventLog(accelerations),
    )


def test_safe_helpers_and_utilization_buckets() -> None:
    assert _safe_dict({"a": 1}) == {"a": 1}
    assert _safe_dict([]) == {}
    assert _safe_text(" x ") == "x"
    assert _safe_text(None) == ""
    assert _safe_float("1.5") == 1.5
    assert _safe_float("bad", 2.0) == 2.0
    assert _acceleration_batch_utilization_bucket(-1) == "low"
    assert _acceleration_batch_utilization_bucket(0.5) == "medium"
    assert _acceleration_batch_utilization_bucket(2) == "high"


def test_empty_service_returns_read_only_zero_summary() -> None:
    service = _service(with_audit=False)
    assert service._selection_records() == ()
    assert service._verification_records() == ()
    assert service._closed_loop_records() == ()
    assert service._provider_mix() == ()
    assert service._tier_mix() == ()
    assert service._burn_summary() == (0.0, 0.0)
    assert service._acceleration_summary()["event_count"] == 0
    result = service.build()
    assert result["tenant_id"] is None
    assert result["tenant_bound"] is False
    assert result["selection_count"] == 0
    assert result["providers"][0]["provider_name"] == "p1"


def test_action_records_build_provider_tier_verification_and_escalation_summary() -> None:
    records = [
        {"tenant_id": "tenant-a", "payload": {"stage": "inference.capacity_selection", "provider_name": "p1", "capacity_tier": "fast", "estimated_cost_usd": "1.25"}},
        {"tenant_id": "tenant-a", "payload": {"stage": "inference.capacity_selection", "provider_name": "p1", "capacity_tier": "ignored-later", "estimated_cost_usd": "bad"}},
        {"tenant_id": "tenant-a", "payload": {"stage": "inference.capacity_selection"}},
        {"tenant_id": "tenant-a", "payload": {"stage": "inference.verification", "accepted": True, "verification_reason": "ok"}},
        {"tenant_id": "tenant-a", "payload": {"stage": "inference.verification", "accepted": False}},
        {"tenant_id": "tenant-a", "status": "done", "recorded_at": "now", "payload": {"stage": "closed_loop.run_cycle", "inference_provider_name": "p1"}},
        {"tenant_id": "tenant-a", "payload": {"stage": "closed_loop.run_cycle"}},
        {"tenant_id": "tenant-b", "payload": {"stage": "inference.capacity_selection", "provider_name": "foreign", "estimated_cost_usd": 99}},
        {"tenant_id": "tenant-a", "payload": "not-map"},
    ]
    service = _service(records=records)
    provider_mix = service._provider_mix(tenant_id="tenant-a")
    assert provider_mix[0] == {"provider_name": "p1", "traffic_share": 0.666667, "tier": "fast", "selection_count": 2, "estimated_cost_usd": 1.25}
    assert provider_mix[1]["provider_name"] == "unknown"
    assert service._tier_mix(tenant_id="tenant-a")[0]["capacity_tier"] == "fast"
    verification = service._verification_summary(tenant_id="tenant-a")
    assert verification["accepted_count"] == 1
    assert verification["rejected_count"] == 1
    assert {item["reason"] for item in verification["top_reasons"]} == {"ok", "unknown"}
    escalations = service._recent_escalations(tenant_id="tenant-a")
    assert escalations == ({"provider_name": "p1", "capacity_tier": None, "status": "done", "recorded_at": "now"},)
    assert service._burn_summary(tenant_id="tenant-a") == (0.0, 1.25)


def test_budget_and_acceleration_events_are_tenant_filtered_and_aggregated() -> None:
    burns = (
        SimpleNamespace(tenant_id="tenant-a", estimated_cost_usd=1.0),
        SimpleNamespace(tenant_id="tenant-b", estimated_cost_usd=100.0),
        SimpleNamespace(tenant_id="tenant-a", estimated_cost_usd=2.5),
    )
    accelerations = (
        SimpleNamespace(tenant_id="tenant-a", execution_mode="gpu", device_class="cuda", transport_kind="pcie", prefers_local_memory=True, batch_items=1, provider_max_batch_items=10, pressure_band="high", locality_scope="local", expected_transfer_overhead_ms=5, saturation_score=2.0, expected_queue_penalty_ms=3),
        SimpleNamespace(tenant_id="tenant-a", execution_mode="", device_class="", transport_kind="", prefers_local_memory=False, batch_items=5, provider_max_batch_items=10, pressure_band="", locality_scope="", expected_transfer_overhead_ms=7, saturation_score=-1.0, expected_queue_penalty_ms=9),
        SimpleNamespace(tenant_id="tenant-a", execution_mode="gpu", device_class="cuda", transport_kind="pcie", prefers_local_memory=True, batch_items=20, provider_max_batch_items=10, pressure_band="high", locality_scope="local", expected_transfer_overhead_ms=9, saturation_score=0.5, expected_queue_penalty_ms=12),
        SimpleNamespace(tenant_id="tenant-b", execution_mode="foreign", device_class="x", transport_kind="x", prefers_local_memory=False, batch_items=1, provider_max_batch_items=1, pressure_band="x", locality_scope="x", expected_transfer_overhead_ms=999, saturation_score=1, expected_queue_penalty_ms=999),
    )
    service = _service(burns=burns, accelerations=accelerations)
    assert service._burn_summary(tenant_id="tenant-a") == (2.5, 3.5)
    assert service._burn_summary(tenant_id="missing") == (0.0, 0.0)
    summary = service._acceleration_summary(tenant_id="tenant-a")
    assert summary["event_count"] == 3
    assert {item["utilization_band"] for item in summary["provider_batch_utilization_mix"]} == {"low", "medium", "high"}
    assert summary["average_batch_items"] == pytest.approx(26 / 3, abs=1e-6)
    assert summary["average_transfer_overhead_ms"] == 7.0
    assert summary["average_saturation_score"] == 0.5
    assert service._acceleration_summary(tenant_id="missing")["event_count"] == 0


def test_build_filters_escalation_count_by_tenant() -> None:
    records = [
        {"tenant_id": "tenant-a", "payload": {"stage": "inference.capacity_selection", "provider_name": "p1", "capacity_tier": "fast", "estimated_cost_usd": 1}},
    ]
    escalations = (
        SimpleNamespace(tenant_id="tenant-a"),
        SimpleNamespace(tenant_id="tenant-b"),
    )
    result = _service(records=records, escalations=escalations).build(tenant_id="tenant-a")
    assert result["tenant_bound"] is True
    assert result["escalation_event_count"] == 1
    assert result["selection_count"] == 1
    assert result["burn_rate_usd_per_hour"] == 1.0
    with pytest.raises(ValueError):
        _service().build(tenant_id=" ")


def test_unfiltered_budget_and_acceleration_branches() -> None:
    burns = (
        SimpleNamespace(tenant_id="tenant-a", estimated_cost_usd=1.0),
        SimpleNamespace(tenant_id="tenant-b", estimated_cost_usd=2.0),
    )
    accelerations = (
        SimpleNamespace(tenant_id="tenant-a", execution_mode="cpu", device_class="cpu", transport_kind="memory", prefers_local_memory=True, batch_items=1, provider_max_batch_items=2, pressure_band="low", locality_scope="local", expected_transfer_overhead_ms=0, saturation_score=0.1, expected_queue_penalty_ms=0),
    )
    service = _service(burns=burns, accelerations=accelerations)
    assert service._burn_summary() == (2.0, 3.0)
    assert service._acceleration_summary()["event_count"] == 1
