from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import execution.closed_loop_orchestrator as sut
from tenancy.tenant_queue_scope import TenantQueueScope


class DictObject:
    def __init__(self, payload):
        self.payload = dict(payload)

    def to_dict(self):
        return dict(self.payload)


class Signal(DictObject):
    pass


class Rows:
    def __init__(self, *payloads):
        self.rows = [DictObject(payload) for payload in payloads]

    def list_rows(self):
        return list(self.rows)


class Policy(DictObject):
    external_confirmation_mode = "strict"


class BudgetVerdict:
    def __init__(self, *, allowed=True, reason="ok", consumed=False):
        self.allowed = allowed
        self.reason = reason
        self.tenant_id = "tenant-a"
        self.violations = () if allowed else ("limit",)
        self.consumed = consumed


class ScopeProfile:
    retention_policy = {"max_age_days": 30}

    def to_dict(self):
        return {"profile_name": "tenant", "retention_policy": self.retention_policy}


class Retention:
    def __init__(self, payload=None):
        self.payload = dict(payload or {"max_age_days": 30})

    def to_dict(self):
        return dict(self.payload)


class StateObject:
    def __init__(self, meta=None):
        self.meta = dict(meta or {})


class OpaqueState:
    pass


def install_module_fakes(
    monkeypatch,
    *,
    recovery=None,
    handoff=None,
    persistence_receipt=None,
):
    monkeypatch.setattr(
        sut,
        "build_action_verification_policy",
        lambda action, default_mode: Policy({"mode": default_mode}),
    )
    monkeypatch.setattr(sut, "expectation_from_action", lambda *args, **kwargs: "expected")
    monkeypatch.setattr(
        sut,
        "autonomy_input_from_world_state",
        lambda mapping, **kwargs: {"mapping": mapping, **kwargs},
    )
    monkeypatch.setattr(
        sut,
        "_stable_reliability_trace",
        lambda **kwargs: {
            "trace_key": "trace-1",
            "semantic_scope": {"operation": "execute"},
        },
    )
    monkeypatch.setattr(
        sut,
        "_build_recovery_summary",
        lambda **kwargs: dict(recovery or {}),
    )
    monkeypatch.setattr(
        sut,
        "_normalize_approval_context",
        lambda **kwargs: dict(kwargs.get("approval_context") or {}),
    )
    monkeypatch.setattr(
        sut,
        "_build_approval_handoff",
        lambda **kwargs: dict(handoff or {}),
    )
    monkeypatch.setattr(sut, "_economic_event_id", lambda **kwargs: "economic-1")
    monkeypatch.setattr(
        sut,
        "_apply_economic_history_to_state",
        lambda world_state, **kwargs: world_state,
    )
    monkeypatch.setattr(
        sut,
        "EconomicRetentionPolicy",
        SimpleNamespace(from_mapping=lambda value: Retention(value)),
    )


def make_cycle_orchestrator(
    *,
    state,
    persistence_receipt,
    tenant_scope,
    budget_verdict,
    verification_error=None,
    signals=(),
    recovery_handoff=True,
):
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    verifier = Mock()
    if verification_error is not None:
        verifier.verify.side_effect = verification_error
    else:
        verifier.verify.return_value = DictObject(
            {
                "verification_status": "verified",
                "verification": {"status": "verified"},
                "economic_safety": {
                    "budget_guard": {
                        "metadata": {"planning_signals": {"risk": 1}},
                        "economic_policy": {"mode": "safe"},
                    },
                    "revenue_verification": {"verified": True},
                },
            }
        )
    obj._evidence_verifier = verifier
    obj._world_state_updater = SimpleNamespace(
        build_update=Mock(return_value=DictObject({"updated": True})),
        apply=Mock(return_value=state),
    )
    obj._evidence_persistence_service = SimpleNamespace(
        build_feedback_artifacts=Mock(
            return_value={
                "memory": {"saved": True},
                "persistence_receipt": dict(persistence_receipt),
            }
        )
    )
    obj._autonomy_policy = SimpleNamespace(
        evaluate=Mock(
            return_value=DictObject(
                {"tier": "supervised", "approval_required": False}
            )
        )
    )
    obj._opportunity_detector = SimpleNamespace(
        detect=Mock(return_value=[Signal(payload) for payload in signals])
    )
    obj._observability_scope = Mock(return_value=nullcontext())
    obj._assert_tenant_consistency = Mock()
    obj._tenant_scope_for = Mock(return_value=tenant_scope)
    obj._resolve_tenant_budget = Mock(return_value=budget_verdict)
    obj._record_cycle_audit = Mock()
    obj._economic_scope_profile_resolver = SimpleNamespace(
        resolve=Mock(return_value=ScopeProfile())
    )
    obj._economic_memory_feedback = SimpleNamespace(
        build=Mock(return_value=SimpleNamespace(to_memory_fact=lambda: {"event_id": "economic-1"}))
    )
    obj._economic_trace_store = SimpleNamespace(
        append_from_results=Mock(return_value=DictObject({"trace_id": "trace"})),
        list_rows=lambda: [],
    )
    obj._economic_metrics_stream = SimpleNamespace(
        record_budget_guard=Mock(),
        record_revenue_verification=Mock(),
        snapshot=Mock(return_value={"events": 1}),
    )
    obj._policy_snapshot_builder = SimpleNamespace(
        build=Mock(return_value=DictObject({"snapshot_id": "snapshot-1"}))
    )
    obj._economic_policy_snapshot_store = SimpleNamespace(
        append_payload=Mock(return_value=DictObject({"snapshot_id": "snapshot-1"})),
        list_rows=lambda: [],
    )
    obj._economic_memory_store = SimpleNamespace(
        upsert_payload=Mock(return_value=DictObject({"event_id": "economic-1"})),
        list_rows=lambda: [],
    )
    obj._roi_history_builder = SimpleNamespace(
        build=Mock(return_value=DictObject({"event_id": "economic-1"}))
    )
    obj._roi_history_store = SimpleNamespace(
        upsert=Mock(return_value=DictObject({"event_id": "economic-1"})),
        list_rows=lambda: [],
    )
    obj._capital_rebalancer = SimpleNamespace(
        build_plan=Mock(return_value=DictObject({"plan": "hold"}))
    )
    obj._economic_metrics_store = SimpleNamespace(
        upsert_payload=Mock(return_value=DictObject({"snapshot_id": "economic-1"})),
        list_rows=lambda: [],
    )
    obj._build_cross_run_economic_audit = Mock(return_value={"audit": True})
    obj._build_economic_audit_bundle = Mock(
        return_value={"bundle_id": "bundle-1", "digest": "sha", "payload": {}}
    )
    obj._write_economic_audit_bundle = Mock(
        return_value={"path": "/bundle", "bundle_name": "bundle-1"}
    )
    obj._economic_audit_bundle_service = SimpleNamespace(
        build_export_manifest=Mock(return_value={"manifest": True})
    )
    obj._economic_store_bundle = SimpleNamespace(node_id="node-a")
    obj._build_economic_bundle_reconciliation = Mock(
        return_value={"consistent": True}
    )
    obj._economic_recovery_handoff = SimpleNamespace(
        build=Mock(
            return_value=(DictObject({"run_id": "run-1"}) if recovery_handoff else None)
        )
    )
    return obj


def test_run_cycle_projects_all_optional_contexts_and_object_state(monkeypatch):
    agi_signals = [
        {"signal_type": "agi", "title": "A", "rationale": "R"},
        "not-a-mapping",
    ]
    state = StateObject(
        {
            "decision_agi": {
                "selected_goal": {"goal": "Grow", "goal_family": "Revenue"},
                "planning_horizon": "week",
                "planning_ttl": 3,
                "strategy_hints": [{"kind": "offer"}],
                "opportunity_signals": agi_signals,
            }
        }
    )
    detector_signals = [
        {"signal_type": "base", "title": "duplicate", "rationale": "same"},
        {"signal_type": "base", "title": "duplicate", "rationale": "same"},
    ] + [
        {"signal_type": "base", "title": f"signal-{index}", "rationale": "x"}
        for index in range(20)
    ]
    receipt = {
        "effect_key": "effect-1",
        "outbox_message_id": "message-1",
        "outbox_state": "delivered",
        "outbox_topic": "effects",
        "outbox_backend_name": "postgres",
        "outbox_external_id": "external-1",
        "outbox_delivered_at": "2026-07-26T00:00:00Z",
        "delivery_guarantee": "exactly-once",
        "runtime_effect_delivery": {"ok": True},
        "outbox_delivery_metadata": {"attempt": 1},
    }
    install_module_fakes(
        monkeypatch,
        recovery={"mode": "resume"},
        handoff={"operator": "required"},
        persistence_receipt=receipt,
    )
    monkeypatch.setattr(sut, "apply_feedback_to_world_state", lambda **kwargs: state)
    tenant_scope = TenantQueueScope(
        tenant_id="tenant-a", queue_name="queue-a", namespace="runtime"
    )
    budget = BudgetVerdict(allowed=True, consumed=True)
    orchestrator = make_cycle_orchestrator(
        state=state,
        persistence_receipt=receipt,
        tenant_scope=tenant_scope,
        budget_verdict=budget,
        signals=detector_signals,
    )
    cycle_input = sut.ClosedLoopCycleInput(
        action={
            "tenant_id": "tenant-a",
            "queue_name": "queue-a",
            "run_id": "run-1",
            "decision_id": "decision-1",
            "action_id": "action-1",
            "action_type": "send_message",
        },
        world_state=state,
        execution_receipt={
            "inference_provider_name": "provider-a",
            "inference_capacity_tier": "premium",
            "inference_estimated_cost_usd": 0.2,
            "inference_verification_mode": "strict",
        },
        approval_required=True,
        approval_context={"approval_required": True, "operator_required": True},
        capability_context={"capability": "send"},
        replanning_context={"reason": "capacity"},
    )

    result = orchestrator.run_cycle(cycle_input=cycle_input)

    persisted = result.persisted_memory_evidence
    assert persisted["tenant_scope"]["scope_key"] == tenant_scope.scope_key
    assert persisted["tenant_budget"]["consumed"] is True
    assert persisted["recovery"] == {"mode": "resume"}
    assert persisted["approval"]["operator_required"] is True
    assert persisted["inference_runtime"]["provider_name"] == "provider-a"
    assert persisted["capability"] == {"capability": "send"}
    assert persisted["capability_replanning"] == {"reason": "capacity"}
    assert persisted["decision_agi"]["selected_goal"] == "Grow"
    assert result.next_tier_context["operator_handoff"] == {
        "operator": "required"
    }
    assert len(result.opportunity_signals) == 16
    assert result.world_state.meta["economic_recovery_handoff"] == {
        "run_id": "run-1"
    }
    assert orchestrator._record_cycle_audit.call_args_list[-1].kwargs["status"] == "succeeded"


def test_run_cycle_covers_empty_optional_paths_and_opaque_state(monkeypatch):
    state = OpaqueState()
    install_module_fakes(monkeypatch, recovery={}, handoff={})
    monkeypatch.setattr(sut, "apply_feedback_to_world_state", lambda **kwargs: state)
    orchestrator = make_cycle_orchestrator(
        state=state,
        persistence_receipt={},
        tenant_scope=None,
        budget_verdict=None,
        signals=(),
        recovery_handoff=False,
    )
    cycle_input = sut.ClosedLoopCycleInput(
        action={"action_type": "noop", "action_id": "action-1"},
        world_state=state,
        approval_context={"approval_required": True},
    )

    result = orchestrator.run_cycle(cycle_input=cycle_input)

    assert result.world_state is state
    assert "tenant_scope" not in result.persisted_memory_evidence
    assert "tenant_budget" not in result.persisted_memory_evidence
    assert "operator_handoff" not in result.next_tier_context
    assert "decision_agi" not in result.next_tier_context
    assert result.opportunity_signals == ()


def test_run_cycle_records_failed_audit_and_reraises(monkeypatch):
    state = {}
    install_module_fakes(monkeypatch)
    monkeypatch.setattr(sut, "apply_feedback_to_world_state", lambda **kwargs: state)
    orchestrator = make_cycle_orchestrator(
        state=state,
        persistence_receipt={},
        tenant_scope=None,
        budget_verdict=None,
        verification_error=RuntimeError("verification failed"),
    )

    with pytest.raises(RuntimeError, match="verification failed"):
        orchestrator.run_cycle(
            cycle_input=sut.ClosedLoopCycleInput(
                action={"action_type": "send", "action_id": "action-1"}
            )
        )
    assert orchestrator._record_cycle_audit.call_args_list[-1].kwargs["status"] == "failed"


def test_observability_scope_and_cycle_audit_contract(monkeypatch):
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    obj._event_log = "events"
    obj._execution_trace_store = "traces"
    assert obj._observability_scope(action={}, execution_receipt={}).__class__ is nullcontext().__class__

    span = object()
    capture = Mock(return_value=span)
    monkeypatch.setattr(sut, "execution_span", capture)
    action = {
        "tenant_id": "tenant-a",
        "run_id": "run-1",
        "decision_id": "decision-1",
        "correlation_id": "correlation-1",
        "action_id": "action-1",
    }
    assert obj._observability_scope(action=action, execution_receipt={}) is span
    failure_builder = capture.call_args.kwargs["failure_payload_builder"]
    assert failure_builder(ValueError("bad")) == {
        "error": "ValueError",
        "message": "bad",
    }

    audit = SimpleNamespace(record_stage=Mock())
    obj._action_audit_log = audit
    obj._record_cycle_audit(
        action={"tenant_id": "tenant-a"},
        execution_receipt={},
        status="ignored",
    )
    audit.record_stage.assert_not_called()
    obj._record_cycle_audit(
        action={
            "tenant_id": "tenant-a",
            "action_id": "action-1",
            "action_type": "send",
            "decision_id": "decision-1",
            "trace_id": "trace-1",
        },
        execution_receipt={},
        status="succeeded",
        payload={"ok": True},
    )
    assert audit.record_stage.call_args.kwargs["stage"] == "closed_loop.run_cycle"
    assert audit.record_stage.call_args.kwargs["payload"] == {"ok": True}


def test_tenant_consistency_rejects_cross_tenant_and_queue_mismatch():
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    obj._tenant_registry = None
    with pytest.raises(ValueError, match="cross-tenant"):
        obj._assert_tenant_consistency(
            action={"tenant_id": "tenant-a"},
            execution_receipt={"tenant_id": "tenant-b"},
        )
    with pytest.raises(ValueError, match="queue mismatch"):
        obj._assert_tenant_consistency(
            action={"tenant_id": "tenant-a", "queue_name": "q1"},
            execution_receipt={"tenant_id": "tenant-a", "queue_name": "q2"},
        )


def test_tenant_consistency_validates_registry_qualified_keys_and_declared_scope():
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    registry = SimpleNamespace(assert_active=Mock())
    obj._tenant_registry = registry
    action_scope = TenantQueueScope("tenant-a", "queue-a", "runtime")
    receipt_scope = TenantQueueScope("tenant-a", "queue-a", "runtime")
    action = {
        "tenant_id": "tenant-a",
        "queue_name": "queue-a",
        "qualified_job_id": action_scope.qualify_job_id("job-1"),
        "qualified_dedupe_key": action_scope.qualify_dedupe_key("dedupe-1"),
        "tenant_scope": {
            "tenant_id": "tenant-a",
            "queue_name": "queue-a",
            "namespace": "runtime",
            "scope_key": action_scope.scope_key,
        },
    }
    receipt = {
        "tenant_id": "tenant-a",
        "queue_name": "queue-a",
        "qualified_job_id": receipt_scope.qualify_job_id("job-1"),
        "qualified_dedupe_key": receipt_scope.qualify_dedupe_key("dedupe-1"),
        "tenant_scope": {
            "tenant_id": "tenant-a",
            "queue_name": "queue-a",
            "namespace": "runtime",
            "scope_key": receipt_scope.scope_key,
        },
    }

    obj._assert_tenant_consistency(action=action, execution_receipt=receipt)
    registry.assert_active.assert_called_once_with("tenant-a")

    # Keep both scopes present while omitting qualified ids so each loop also
    # exercises its false branch and advances to the next key.
    obj._assert_tenant_consistency(
        action={
            "tenant_id": "tenant-a",
            "queue_name": "queue-a",
            "tenant_scope": action["tenant_scope"],
        },
        execution_receipt={
            "tenant_id": "tenant-a",
            "queue_name": "queue-a",
            "tenant_scope": receipt["tenant_scope"],
        },
    )

    bad_action = {**action, "tenant_scope": {**action["tenant_scope"], "scope_key": "wrong"}}
    with pytest.raises(ValueError, match="action tenant scope_key mismatch"):
        obj._assert_tenant_consistency(action=bad_action, execution_receipt={})

    bad_receipt = {**receipt, "tenant_scope": {**receipt["tenant_scope"], "scope_key": "wrong"}}
    with pytest.raises(ValueError, match="receipt tenant scope_key mismatch"):
        obj._assert_tenant_consistency(action={}, execution_receipt=bad_receipt)

    different_namespace = {
        **receipt,
        "tenant_scope": {
            "tenant_id": "tenant-a",
            "queue_name": "queue-a",
            "namespace": "other",
            "scope_key": TenantQueueScope("tenant-a", "queue-a", "other").scope_key,
        },
        "qualified_job_id": TenantQueueScope("tenant-a", "queue-a", "other").qualify_job_id("job-1"),
        "qualified_dedupe_key": TenantQueueScope("tenant-a", "queue-a", "other").qualify_dedupe_key("dedupe-1"),
    }
    with pytest.raises(ValueError, match="tenant scope mismatch"):
        obj._assert_tenant_consistency(action=action, execution_receipt=different_namespace)


def test_tenant_scope_resolution_and_budget_paths(monkeypatch):
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    obj._tenant_registry = None
    assert obj._tenant_scope_for(action={}, execution_receipt={}) is None
    scope = obj._tenant_scope_for(
        action={
            "tenant_scope": {
                "tenant_id": "tenant-a",
                "queue_name": "queue-a",
                "namespace": "custom",
            }
        },
        execution_receipt={},
    )
    assert scope == TenantQueueScope("tenant-a", "queue-a", "custom")

    obj._tenant_execution_budget_guard = None
    assert obj._resolve_tenant_budget(action={}, execution_receipt={}) is None
    receipt_verdict = obj._resolve_tenant_budget(
        action={},
        execution_receipt={
            "tenant_budget": {
                "allowed": True,
                "reason": "receipt",
                "tenant_id": "tenant-a",
                "violations": [],
                "consumed": True,
            }
        },
    )
    assert receipt_verdict.allowed is True
    assert obj._budget_verdict_dict(receipt_verdict)["consumed"] is True

    usage_factory = Mock(return_value="usage")
    monkeypatch.setattr(
        sut,
        "TenantExecutionBudgetGuard",
        SimpleNamespace(from_execution_payload=usage_factory),
    )
    guard = SimpleNamespace(
        evaluate=Mock(return_value=BudgetVerdict(allowed=True)),
        consume=Mock(return_value=BudgetVerdict(allowed=True, consumed=True)),
    )
    obj._tenant_execution_budget_guard = guard
    assert obj._resolve_tenant_budget(
        action={"tenant_id": "tenant-a"}, execution_receipt={}
    ).allowed is True
    guard.evaluate.assert_called_once_with(usage="usage")
    assert obj._resolve_tenant_budget(
        action={"tenant_id": "tenant-a", "tenant_budget_mode": "consume"},
        execution_receipt={},
    ).consumed is True
    guard.consume.assert_called_once_with(usage="usage")

    guard.evaluate.return_value = BudgetVerdict(allowed=False, reason="limit")
    with pytest.raises(RuntimeError, match="tenant_execution_budget_denied:limit"):
        obj._resolve_tenant_budget(
            action={"tenant_id": "tenant-a"}, execution_receipt={}
        )


def install_reconciliation_validators(monkeypatch, *, failure=None):
    class Verdict:
        def __init__(self, *, valid=True, supported=True, reason=""):
            self.valid = valid
            self.supported = supported
            self.reason = reason

        def to_dict(self):
            return {
                "valid": self.valid,
                "supported": self.supported,
                "reason": self.reason,
            }

    verdicts = {
        "migration": Verdict(supported=failure != "migration", reason="migration bad"),
        "monotonicity": Verdict(valid=failure != "monotonicity", reason="mono bad"),
        "lineage": Verdict(valid=failure != "lineage", reason="lineage bad"),
        "immutability": Verdict(valid=failure != "immutability", reason="immutable bad"),
    }
    monkeypatch.setattr(
        sut,
        "EconomicSchemaValidator",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        sut,
        "EconomicSchemaMigrationMatrix",
        lambda: SimpleNamespace(validate=lambda **kwargs: verdicts["migration"]),
    )
    monkeypatch.setattr(
        sut,
        "EconomicSegmentValidator",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        sut,
        "EconomicSemanticValidator",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        sut,
        "EconomicScopeLineageGuard",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        sut,
        "EconomicReplayEpochGuard",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        sut,
        "EconomicStateMonotonicityGuard",
        lambda: SimpleNamespace(validate=lambda **kwargs: verdicts["monotonicity"]),
    )
    monkeypatch.setattr(
        sut,
        "EconomicLineageLockBuilder",
        lambda: SimpleNamespace(validate=lambda **kwargs: verdicts["lineage"]),
    )
    monkeypatch.setattr(
        sut,
        "EconomicBundleImmutabilityValidator",
        lambda: SimpleNamespace(validate=lambda **kwargs: verdicts["immutability"]),
    )


def make_reconciliation_orchestrator(*, consistent=True):
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    rows = Rows({"row": 1})
    obj._economic_memory_store = rows
    obj._roi_history_store = rows
    obj._economic_policy_snapshot_store = rows
    obj._economic_trace_store = rows
    obj._economic_metrics_store = rows
    obj._economic_store_bundle = SimpleNamespace(node_id="node-a")
    obj._economic_audit_bundle_service = SimpleNamespace(
        restore_bundle=Mock(
            return_value={
                "bundle_id": "restored",
                "payload": {
                    "export_manifest": {
                        "scope": {"profile_name": "tenant"},
                        "scope_lineage": {},
                        "bundle_schema_version": "1",
                    },
                    "metadata": {},
                },
            }
        )
    )
    obj._economic_multi_backend_reconciliation = SimpleNamespace(
        build=Mock(
            return_value=DictObject(
                {"consistent": consistent, "metadata": {"quorum_failure_segments": []}}
            )
        )
    )
    obj._economic_forensics_service = SimpleNamespace(record_event=Mock())
    return obj


def call_reconciliation(monkeypatch, *, failure=None, bundle_path=True, consistent=True):
    install_reconciliation_validators(monkeypatch, failure=failure)
    obj = make_reconciliation_orchestrator(consistent=consistent)
    result = obj._build_economic_bundle_reconciliation(
        bundle={
            "bundle_id": "bundle-1",
            "digest": "sha",
            "payload": {
                "export_manifest": {
                    "scope": {"profile_name": "tenant"},
                    "bundle_schema_version": "1",
                }
            },
        },
        bundle_entry={"path": "/bundle"} if bundle_path else None,
    )
    return obj, result


def test_orchestrator_reconciliation_in_memory_and_restored_success(monkeypatch):
    obj, memory = call_reconciliation(monkeypatch, bundle_path=False, consistent=True)
    assert memory["import_validation"]["source"] == "in_memory_bundle"
    assert obj._economic_forensics_service.record_event.call_args.kwargs["severity"] == "info"

    obj, restored = call_reconciliation(monkeypatch, bundle_path=True, consistent=False)
    assert restored["import_validation"]["status"] == "valid"
    assert obj._economic_forensics_service.record_event.call_args.kwargs["severity"] == "warning"


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("migration", "migration bad"),
        ("monotonicity", "mono bad"),
        ("lineage", "lineage bad"),
        ("immutability", "immutable bad"),
    ],
)
def test_orchestrator_reconciliation_rejects_invalid_restores(
    monkeypatch, failure, message
):
    obj, result = call_reconciliation(monkeypatch, failure=failure)
    assert result["import_validation"]["valid"] is False
    assert message in result["import_validation"]["issues"][0]


def test_extract_economic_payload_precedence_and_empty_result():
    assert sut.ClosedLoopOrchestrator._extract_economic_payload(
        action={
            "economic_safety": {
                "budget_guard": {"source": "nested"},
                "revenue_verification": {"verified": True},
            }
        },
        execution_receipt={},
        verification={},
        persisted_payload={},
    ) == ({"source": "nested"}, {"verified": True})
    assert sut.ClosedLoopOrchestrator._extract_economic_payload(
        action={},
        execution_receipt={"budget_guard": {"source": "direct"}},
        verification={},
        persisted_payload={},
    ) == ({"source": "direct"}, {})
    assert sut.ClosedLoopOrchestrator._extract_economic_payload(
        action={}, execution_receipt={}, verification={}, persisted_payload={}
    ) == ({}, {})


def test_constructor_covers_default_explicit_and_wired_store_paths(monkeypatch, tmp_path):
    default = sut.ClosedLoopOrchestrator()
    assert default._economic_store_bundle is None
    assert default._tenant_execution_budget_guard is None

    supplied = {
        "evidence_verifier": object(),
        "world_state_updater": object(),
        "evidence_persistence_service": object(),
        "autonomy_policy": object(),
        "opportunity_detector": object(),
        "tenant_execution_budget_guard": object(),
        "tenant_registry": object(),
        "event_log": object(),
        "execution_trace_store": object(),
        "action_audit_log": object(),
        "economic_trace_store": object(),
        "economic_metrics_stream": object(),
        "economic_metrics_store": object(),
        "economic_policy_snapshot_store": object(),
        "economic_memory_store": object(),
        "roi_history_store": object(),
    }
    explicit = sut.ClosedLoopOrchestrator(**supplied)
    assert explicit._evidence_verifier is supplied["evidence_verifier"]
    assert explicit._economic_trace_store is supplied["economic_trace_store"]
    assert explicit._roi_history_store is supplied["roi_history_store"]

    bundle = SimpleNamespace(
        forensics_store=object(),
        quarantine_store=object(),
        retention_policy={"max_age_days": 7},
        trace_store=object(),
        metrics_store=object(),
        policy_snapshot_store=object(),
        memory_store=object(),
        roi_history_store=object(),
    )
    wiring = SimpleNamespace(build=Mock(return_value=bundle))
    factory = Mock(return_value=wiring)
    monkeypatch.setattr(sut, "EconomicStoreWiring", factory)
    wired = sut.ClosedLoopOrchestrator(economic_storage_root=tmp_path)
    factory.assert_called_once_with(root_dir=tmp_path)
    assert wired._economic_store_bundle is bundle
    assert wired._economic_trace_store is bundle.trace_store
    assert wired._economic_metrics_store is bundle.metrics_store
    assert wired._economic_policy_snapshot_store is bundle.policy_snapshot_store
    assert wired._economic_memory_store is bundle.memory_store
    assert wired._roi_history_store is bundle.roi_history_store


def test_cycle_audit_returns_when_logger_is_missing_or_incompatible():
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    obj._action_audit_log = None
    obj._record_cycle_audit(
        action={"tenant_id": "tenant-a", "action_id": "a", "action_type": "send"},
        execution_receipt={},
        status="ignored",
    )
    obj._action_audit_log = object()
    obj._record_cycle_audit(
        action={"tenant_id": "tenant-a", "action_id": "a", "action_type": "send"},
        execution_receipt={},
        status="ignored",
    )


def run_state_projection_case(monkeypatch, *, state, recovery_handoff, approval_context=None):
    install_module_fakes(monkeypatch, recovery={}, handoff={})
    monkeypatch.setattr(sut, "apply_feedback_to_world_state", lambda **kwargs: state)
    orchestrator = make_cycle_orchestrator(
        state=state,
        persistence_receipt={},
        tenant_scope=None,
        budget_verdict=None,
        signals=(),
        recovery_handoff=recovery_handoff,
    )
    return orchestrator.run_cycle(
        cycle_input=sut.ClosedLoopCycleInput(
            action={"action_type": "noop", "action_id": "action-1"},
            world_state=state,
            approval_context=dict(approval_context or {}),
        )
    )


def test_run_cycle_covers_mapping_state_and_empty_approval_branches(monkeypatch):
    mapping_with_handoff = {"meta": {}}
    result = run_state_projection_case(
        monkeypatch,
        state=mapping_with_handoff,
        recovery_handoff=True,
        approval_context={},
    )
    assert result.world_state["meta"]["economic_recovery_handoff"] == {
        "run_id": "run-1"
    }
    assert "approval" not in result.persisted_memory_evidence
    assert "approval" not in result.next_tier_context

    mapping_without_handoff = {"meta": {}}
    result = run_state_projection_case(
        monkeypatch,
        state=mapping_without_handoff,
        recovery_handoff=False,
    )
    assert "economic_recovery_handoff" not in result.world_state["meta"]


def test_run_cycle_covers_object_state_without_recovery_handoff(monkeypatch):
    state = StateObject({})
    result = run_state_projection_case(
        monkeypatch,
        state=state,
        recovery_handoff=False,
    )
    assert "economic_recovery_handoff" not in result.world_state.meta


def make_bundle_method_owner(*, with_store_bundle):
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    rows = Rows({"row": 1})
    obj._economic_memory_store = rows
    obj._roi_history_store = rows
    obj._economic_policy_snapshot_store = rows
    obj._economic_trace_store = rows
    obj._economic_metrics_store = rows
    obj._economic_retention_policy = Retention({"max_age_days": 30})
    obj._economic_store_bundle = (
        SimpleNamespace(
            node_id="node-a",
            root_dir="/root",
            bundle_catalog_path="/catalog.jsonl",
        )
        if with_store_bundle
        else None
    )
    obj._economic_audit_bundle_service = SimpleNamespace(
        build_export_manifest=Mock(return_value={"manifest": True}),
        build_bundle=Mock(
            return_value=DictObject(
                {"bundle_id": "bundle-1", "payload": {}, "digest": "sha"}
            )
        ),
        write_bundle=Mock(return_value={"path": "/bundle"}),
    )
    return obj


def test_orchestrator_bundle_methods_cover_default_and_override_paths():
    without_store = make_bundle_method_owner(with_store_bundle=False)
    built = without_store._build_economic_audit_bundle(
        bundle_id="bundle-1",
        audit_summary={"ok": True},
        scope_profile={"profile_name": "tenant"},
    )
    assert built["bundle_id"] == "bundle-1"
    assert without_store._economic_audit_bundle_service.build_export_manifest.call_args.kwargs[
        "node_id"
    ] == "local-primary"
    assert without_store._write_economic_audit_bundle(
        bundle_name="bundle-1", bundle=built
    )["path"] == ""

    with_store = make_bundle_method_owner(with_store_bundle=True)
    override = Retention({"max_age_days": 5})
    built = with_store._build_economic_audit_bundle(
        bundle_id="bundle-2",
        retention_policy=override,
    )
    assert with_store._economic_audit_bundle_service.build_export_manifest.call_args.kwargs[
        "retention"
    ] == {"max_age_days": 5}
    written = with_store._write_economic_audit_bundle(
        bundle_name="bundle-2", bundle=built
    )
    assert written == {"path": "/bundle"}
    assert with_store._economic_audit_bundle_service.write_bundle.call_args.kwargs[
        "root_dir"
    ] == "/root"


def test_orchestrator_cross_run_audit_covers_real_and_missing_store_readers():
    obj = object.__new__(sut.ClosedLoopOrchestrator)
    obj._economic_memory_store = Rows({"kind": "memory"})
    obj._roi_history_store = Rows({"kind": "roi"})
    obj._economic_policy_snapshot_store = Rows({"kind": "snapshot"})
    obj._cross_run_economic_audit = SimpleNamespace(
        build=Mock(return_value=DictObject({"audit": True}))
    )
    assert obj._build_cross_run_economic_audit() == {"audit": True}
    call = obj._cross_run_economic_audit.build.call_args.kwargs
    assert call["feedback_rows"] == ({"kind": "memory"},)

    obj._economic_memory_store = object()
    obj._roi_history_store = object()
    obj._economic_policy_snapshot_store = object()
    assert obj._build_cross_run_economic_audit() == {"audit": True}
    call = obj._cross_run_economic_audit.build.call_args.kwargs
    assert call == {"feedback_rows": (), "roi_rows": (), "snapshot_rows": ()}
