from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from application.autonomy.autonomy_state_assembly import AutonomyStateAssembly
from application.business_autonomy.provider_admin_contract import ProviderActivationStatus
from application.business_autonomy.provider_truth_matrix import provider_quota_truth_map, provider_runtime_metrics_truth_map
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_sync_history import InMemoryProviderSyncHistoryStore, ProviderSyncHistory
from runtime.platform.event_store.memory_event_store import MemoryEventStore


@dataclass(frozen=True)
class _State:
    meta: dict


class _StateMapper:
    def to_world_state(self, **_kwargs):
        return _State(meta={})


class _Trace:
    run_id = "run-phase10"

    def record(self, **_kwargs):
        return None


def _request():
    return SimpleNamespace(tenant_id="tenant-1", business_id="business-1", goal="grow revenue", goal_id="goal-1", meta={})


def _contract(*, events=None, mapper=None, **extra):
    return SimpleNamespace(
        _state_mapper=mapper or _StateMapper(),
        _capability_health_registry=None,
        _capability_health_scoring_service=None,
        _business_memory_state_adapter=None,
        _state_store=None,
        _event_store=events,
        **extra,
    )


def _assemble(contract):
    return AutonomyStateAssembly(contract=contract).assemble_state(
        request=_request(), trace=_Trace(), step_index=0, previous_feedback={}, business_memory_context={}
    )


def _telegram(state):
    return {row["capability_id"]: row for row in state.meta["capability_discovery"]}["interaction.telegram"]


def _activate_telegram(*, events, tmp_path, recorded_at="2026-09-28T12:00:00+00:00", reason="ok"):
    store = FileProviderActivationStore(FileDistributedDocumentStore(tmp_path / "documents"), event_store=events)
    store.put(ProviderActivationStatus(
        tenant_id="tenant-1", business_id="business-1", provider_key="telegram_bot", connected=True,
        connector_id="telegram", title="Telegram", channel_kind="chatbot", secret_fields_bound=("bot_token",),
        last_updated_utc=recorded_at, governance_enabled=True, persistent_surfaces=("provider_activation",),
        onboarding_ready=True, metadata={"health_probe": {"status": "probe_live_ok", "probe_mode": "live", "reason": reason}},
    ))


def _history():
    return ProviderSyncHistory(InMemoryProviderSyncHistoryStore())


def _append_history(history, *, now, accepted, latency, minutes=0, days=0, business_id="business-1"):
    history.append({
        "tenant_id": "tenant-1", "business_id": business_id, "provider_key": "telegram_bot", "mode": "live",
        "accepted": accepted, "transport_latency_ms": latency,
        "recorded_at_utc": (now - timedelta(minutes=minutes, days=days)).isoformat(),
    })


def test_capability_discovery_is_present_before_headless_decision_planning():
    discovery = tuple(_assemble(_contract()).meta["capability_discovery"])
    by_id = {row["capability_id"]: row for row in discovery}
    telegram = by_id["interaction.telegram"]
    assert telegram["lifecycle"] == "implemented"
    assert telegram["schema_version"] == 4
    assert isinstance(telegram["registry_sources"], list)
    assert telegram["evidence"]
    assert telegram["provider_keys"] == ["telegram_bot"]
    assert telegram["health"] == "unknown"
    assert telegram["availability"] == "unknown"
    assert telegram["approval_requirements"]["owner_approval"] is True
    assert len(by_id) == len(discovery)


def test_capability_discovery_reads_live_provider_truth_before_decision(tmp_path):
    events = MemoryEventStore()
    _activate_telegram(events=events, tmp_path=tmp_path, reason="provider_live_probe_ok")
    telegram = _telegram(_assemble(_contract(events=events)))
    assert telegram["availability"] == "available"
    assert telegram["health"] == "healthy"
    assert telegram["provider_runtime"][0]["source"] == "event_spine.provider_activation"


def test_capability_discovery_reads_durable_provider_metrics_before_decision(tmp_path):
    events = MemoryEventStore()
    _activate_telegram(events=events, tmp_path=tmp_path)
    history, now = _history(), datetime.now(UTC)
    _append_history(history, now=now, accepted=True, latency=100.0, minutes=2)
    _append_history(history, now=now, accepted=False, latency=300.0, minutes=1)
    _append_history(history, now=now, accepted=True, latency=1.0, business_id="other-business")
    telegram = _telegram(_assemble(_contract(events=events, _provider_sync_history=history)))
    assert telegram["reliability"] == 0.5
    assert telegram["latency_ms"] == 290.0
    assert telegram["provider_metrics"][0]["source"] == "provider_sync_history"
    assert telegram["provider_metrics"][0]["sample_count"] == 2


class _QuotaGuard:
    def __init__(self, blocked_connector_ids=()):
        self.blocked = set(blocked_connector_ids)

    def check(self, *, tenant_id, connector_id, requested_calls=1.0):
        blocked = connector_id in self.blocked
        return SimpleNamespace(
            allowed=not blocked, remaining=0.0 if blocked else 9.0,
            reason="quota exceeded" if blocked else "ok", retry_after_seconds=3600 if blocked else None,
        )


def test_capability_discovery_reads_quota_truth_before_decision(tmp_path):
    events = MemoryEventStore()
    _activate_telegram(events=events, tmp_path=tmp_path, recorded_at="2026-09-29T12:00:00+00:00")
    telegram = _telegram(_assemble(_contract(events=events, _provider_quota_guard=_QuotaGuard({"telegram"}))))
    assert telegram["availability"] == "unavailable"
    assert telegram["health"] == "healthy"
    assert telegram["provider_quota"][0]["allowed"] is False
    assert telegram["provider_quota"][0]["remaining"] == 0.0


def test_provider_quota_truth_uses_canonical_provider_connector_id():
    truth = provider_quota_truth_map(
        quota_guard=_QuotaGuard({"telegram"}), tenant_id="tenant-1", provider_keys=("telegram_bot",)
    )
    assert truth["telegram_bot"]["connector_id"] == "telegram"
    assert truth["telegram_bot"]["source"] == "connector_quota_guard"


class _ActionHealthStateMapper:
    def to_world_state(self, **_kwargs):
        return _State(meta={"runtime_capabilities": {"send_message@v1": {
            "enabled": True, "healthy": True, "health_score": 1.0, "health_tier": "healthy",
            "routing_state": "enabled", "source": "capability_health_registry",
        }}})


def test_action_level_health_does_not_forge_provider_specific_discovery_health():
    state = _assemble(_contract(mapper=_ActionHealthStateMapper()))
    assert state.meta["runtime_capabilities"]["send_message@v1"]["health_tier"] == "healthy"
    discovery = {row["capability_id"]: row for row in state.meta["capability_discovery"]}
    assert discovery["interaction.telegram"]["health"] == "unknown"
    assert discovery["interaction.whatsapp"]["health"] == "unknown"
    assert discovery["interaction.email"]["health"] == "unknown"


def test_durable_provider_metrics_reject_corrupt_latency_history():
    now, history = datetime(2026, 9, 29, 12, 0, tzinfo=UTC), _history()
    _append_history(history, now=now, accepted=True, latency=float("nan"), minutes=1)
    with pytest.raises(ValueError, match="transport_latency_ms"):
        provider_runtime_metrics_truth_map(
            sync_history=history, tenant_id="tenant-1", business_id="business-1",
            provider_keys=("telegram_bot",), now_utc=now,
        )


def test_durable_provider_metrics_ignore_stale_history():
    now, history = datetime(2026, 9, 29, 12, 0, tzinfo=UTC), _history()
    _append_history(history, now=now, accepted=False, latency=900.0, days=4)
    _append_history(history, now=now, accepted=True, latency=100.0, minutes=5)
    truth = provider_runtime_metrics_truth_map(
        sync_history=history, tenant_id="tenant-1", business_id="business-1",
        provider_keys=("telegram_bot",), now_utc=now,
    )["telegram_bot"]
    assert truth["sample_count"] == 1
    assert truth["reliability"] == 1.0
    assert truth["error_rate"] == 0.0
    assert truth["latency_ms"] == 100.0
    assert truth["window_seconds"] == 259200
