from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import execution.closed_loop_orchestrator as orchestrator
import execution.closed_loop_orchestrator_economic as economic
import execution.closed_loop_orchestrator_support as support


class DictObject:
    def __init__(self, payload):
        self.payload = dict(payload)

    def to_dict(self):
        return dict(self.payload)


class Rows:
    def __init__(self, *payloads):
        self.rows = [DictObject(payload) for payload in payloads]

    def list_rows(self):
        return list(self.rows)


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


def test_support_compatibility_delegates_to_canonical_owners(monkeypatch):
    safe_dict = Mock(return_value={"safe": True})
    safe_int = Mock(return_value=7)
    stable = Mock(return_value={"trace_key": "trace"})
    event_id = Mock(return_value="event-1")
    apply_history = Mock(return_value="state")
    recovery = Mock(return_value={"status": "recover"})
    normalize = Mock(return_value={"approval_required": True})
    handoff = Mock(return_value={"operator": True})

    monkeypatch.setattr(support, "_safe_dict_owner", safe_dict)
    monkeypatch.setattr(support, "_safe_int_owner", safe_int)
    monkeypatch.setattr(support, "_stable_reliability_trace_owner", stable)
    monkeypatch.setattr(support, "_economic_event_id_owner", event_id)
    monkeypatch.setattr(support, "_apply_economic_history_to_state_owner", apply_history)
    monkeypatch.setattr(support, "_build_recovery_summary_owner", recovery)
    monkeypatch.setattr(support, "_normalize_approval_context_owner", normalize)
    monkeypatch.setattr(support, "_build_approval_handoff_owner", handoff)

    assert support._safe_dict("x") == {"safe": True}
    assert support._safe_int("7") == 7
    assert support._stable_reliability_trace(
        action={"a": 1}, verification={"v": 1}, execution_receipt={"r": 1}
    ) == {"trace_key": "trace"}
    assert support._economic_event_id(
        action={"a": 1}, persisted_payload={"p": 1}, reliability_trace={"t": 1}
    ) == "event-1"
    assert support._apply_economic_history_to_state(
        world_state="old",
        economic_feedback={"f": 1},
        roi_history={"r": 1},
        policy_snapshot={"p": 1},
    ) == "state"
    assert support._build_recovery_summary(
        execution_receipt={"r": 1}, reliability_trace={"t": 1}
    ) == {"status": "recover"}
    assert support._normalize_approval_context(
        action={"a": 1}, execution_receipt={"r": 1}, approval_context={"c": 1}
    ) == {"approval_required": True}
    assert support._build_approval_handoff(
        action={"a": 1}, approval_context={"c": 1}, next_tier={"n": 1}
    ) == {"operator": True}

    safe_dict.assert_called_once_with("x")
    safe_int.assert_called_once_with("7")


def test_safe_list_and_inference_context_cover_all_input_shapes():
    assert support._safe_list([1, 2]) == [1, 2]
    assert support._safe_list((1, 2)) == [1, 2]
    assert set(support._safe_list({1, 2})) == {1, 2}
    assert support._safe_list("no") == []

    receipt = {
        "inference_provider_name": " provider ",
        "inference_capacity_tier": " premium ",
        "inference_estimated_cost_usd": 1.5,
        "inference_verification_mode": "strict",
    }
    assert support._extract_inference_runtime_context(
        action={"inference_provider_name": "fallback"}, execution_receipt=receipt
    ) == {
        "provider_name": "provider",
        "capacity_tier": "premium",
        "estimated_cost_usd": 1.5,
        "verification_mode": "strict",
    }
    assert support._extract_inference_runtime_context(
        action={"inference_capacity_tier": "burst"}, execution_receipt={}
    ) == {
        "provider_name": None,
        "capacity_tier": "burst",
        "estimated_cost_usd": None,
        "verification_mode": None,
    }
    assert support._extract_inference_runtime_context(
        action={}, execution_receipt={}
    ) == {}


def test_decision_agi_extraction_and_compaction_cover_fallbacks():
    class State:
        meta = {"decision_agi": {"selected_goal": {"goal": "Grow"}}}

    assert support._extract_decision_agi_payload(State()) == {
        "selected_goal": {"goal": "Grow"}
    }
    assert support._extract_decision_agi_payload(
        {"meta": {"decision_agi_summary": {"selected_goal": "Retain"}}}
    ) == {"summary": {"selected_goal": "Retain"}}
    assert support._extract_decision_agi_payload({"meta": {}}) == {}

    assert support._planning_ttl_from_horizon(" Day ") == 1
    assert support._planning_ttl_from_horizon("week") == 7
    assert support._planning_ttl_from_horizon("MONTH") == 30
    assert support._planning_ttl_from_horizon("quarter") is None
    assert support._decrement_planning_ttl(None) is None
    assert support._decrement_planning_ttl(0) is None
    assert support._decrement_planning_ttl(1) == 0
    assert support._decrement_planning_ttl("3") == 2

    compact = support._compact_decision_agi_payload(
        {
            "selected_goal": {"goal": " Grow ", "goal_family": " Revenue "},
            "strategy_hints": [{}, {"kind": "offer"}, "bad", {"kind": "ads"}],
            "opportunity_signals": [{"x": 1}, {"x": 2}],
            "planning_horizon": "week",
            "planning_ttl": 3,
            "reasoning_mode": " causal ",
            "suppressed_reasons": ("risk",),
        }
    )
    assert compact == {
        "selected_goal": "Grow",
        "selected_goal_family": "Revenue",
        "planning_horizon": "week",
        "planning_ttl": 2,
        "signal_count": 2,
        "strategy_hints": [{"kind": "offer"}, {"kind": "ads"}],
        "reasoning_mode": "causal",
        "suppressed_reasons": ["risk"],
        "no_second_brain": True,
    }

    fallback = support._compact_decision_agi_payload(
        {
            "summary": {
                "selected_goal": "Retain",
                "selected_goal_family": "Retention",
                "strategy_hints": [{"kind": "message"}],
                "signal_count": "4",
                "planning_horizon": "month",
            }
        }
    )
    assert fallback["planning_ttl"] == 30
    assert fallback["signal_count"] == 4
    assert fallback["strategy_hints"] == [{"kind": "message"}]
    assert support._compact_decision_agi_payload(None) == {
        "signal_count": 0,
        "no_second_brain": True,
    }


def test_orchestrator_helper_surface_matches_support_owner(monkeypatch):
    monkeypatch.setattr(orchestrator, "_safe_dict_owner", lambda value: {"v": value})
    monkeypatch.setattr(orchestrator, "_safe_int_owner", lambda value: 9)
    monkeypatch.setattr(
        orchestrator,
        "_stable_reliability_trace_owner",
        lambda **kwargs: {"trace_key": "trace"},
    )
    monkeypatch.setattr(
        orchestrator, "_economic_event_id_owner", lambda **kwargs: "event"
    )
    monkeypatch.setattr(
        orchestrator, "_apply_economic_history_to_state_owner", lambda **kwargs: "state"
    )
    monkeypatch.setattr(
        orchestrator, "_build_recovery_summary_owner", lambda **kwargs: {"r": 1}
    )
    monkeypatch.setattr(
        orchestrator, "_normalize_approval_context_owner", lambda **kwargs: {"a": 1}
    )
    monkeypatch.setattr(
        orchestrator, "_build_approval_handoff_owner", lambda **kwargs: {"h": 1}
    )

    assert orchestrator._safe_dict("x") == {"v": "x"}
    assert orchestrator._safe_list([1]) == [1]
    assert orchestrator._safe_list((1,)) == [1]
    assert orchestrator._safe_list({1}) == [1]
    assert orchestrator._safe_list("x") == []
    assert orchestrator._safe_int("9") == 9
    assert orchestrator._stable_reliability_trace(
        action={}, verification={}, execution_receipt={}
    ) == {"trace_key": "trace"}
    assert orchestrator._economic_event_id(
        action={}, persisted_payload={}, reliability_trace={}
    ) == "event"
    assert orchestrator._apply_economic_history_to_state(
        world_state={}, economic_feedback={}, roi_history={}, policy_snapshot={}
    ) == "state"
    assert orchestrator._build_recovery_summary(
        execution_receipt={}, reliability_trace={}
    ) == {"r": 1}
    assert orchestrator._normalize_approval_context(
        action={}, execution_receipt={}, approval_context={}
    ) == {"a": 1}
    assert orchestrator._build_approval_handoff(
        action={}, approval_context={}, next_tier={}
    ) == {"h": 1}


def test_orchestrator_agi_helpers_cover_all_branches():
    assert orchestrator._extract_inference_runtime_context(
        action={"inference_provider_name": "action-provider"}, execution_receipt={}
    )["provider_name"] == "action-provider"
    assert orchestrator._extract_inference_runtime_context(
        action={}, execution_receipt={}
    ) == {}

    class State:
        meta = {"decision_agi": {"selected_goal": {"goal": "Grow"}}}

    assert orchestrator._extract_decision_agi_payload(State())["selected_goal"][
        "goal"
    ] == "Grow"
    assert orchestrator._extract_decision_agi_payload(
        {"meta": {"decision_agi_summary": {"selected_goal": "Retain"}}}
    ) == {"summary": {"selected_goal": "Retain"}}
    assert orchestrator._extract_decision_agi_payload({"meta": {}}) == {}

    assert orchestrator._planning_ttl_from_horizon("day") == 1
    assert orchestrator._planning_ttl_from_horizon("week") == 7
    assert orchestrator._planning_ttl_from_horizon("month") == 30
    assert orchestrator._planning_ttl_from_horizon("other") is None
    assert orchestrator._decrement_planning_ttl(None) is None
    assert orchestrator._decrement_planning_ttl(1) == 0

    compact = orchestrator._compact_decision_agi_payload(
        {
            "selected_goal": {"goal": "Grow", "goal_family": "Revenue"},
            "strategy_hints": [{}, {"kind": "offer"}, {"kind": "ads"}],
            "opportunity_signals": [1, 2],
            "planning_horizon": "day",
            "planning_ttl": 2,
        }
    )
    assert compact["planning_ttl"] == 1
    assert compact["strategy_hints"] == [{"kind": "offer"}, {"kind": "ads"}]
    fallback = orchestrator._compact_decision_agi_payload(
        {"summary": {"signal_count": "3", "planning_horizon": "week"}}
    )
    assert fallback["signal_count"] == 3
    assert fallback["planning_ttl"] == 7


def test_economic_store_mapping_and_bundle_building():
    memory = Rows({"kind": "feedback"})
    roi = Rows({"kind": "roi"})
    snapshots = Rows({"kind": "snapshot"})
    traces = Rows({"kind": "trace"})
    metrics = Rows({"kind": "metric"})
    service = SimpleNamespace(
        build_export_manifest=Mock(return_value={"manifest": True}),
        build_bundle=Mock(return_value=DictObject({"bundle_id": "bundle-1"})),
    )
    retention = SimpleNamespace(to_dict=lambda: {"days": 30})
    override = SimpleNamespace(to_dict=lambda: {"days": 7})
    bundle_store = SimpleNamespace(node_id="node-a")

    mapping = economic.build_economic_store_mapping(
        economic_memory_store=memory,
        roi_history_store=roi,
        economic_policy_snapshot_store=snapshots,
        economic_trace_store=traces,
        economic_metrics_store=metrics,
    )
    assert mapping["memory_store"] is memory

    result = economic.build_economic_audit_bundle(
        economic_audit_bundle_service=service,
        economic_memory_store=memory,
        roi_history_store=roi,
        economic_policy_snapshot_store=snapshots,
        economic_trace_store=traces,
        economic_metrics_store=metrics,
        economic_retention_policy=retention,
        economic_store_bundle=bundle_store,
        bundle_id="bundle-1",
        audit_summary={"ok": True},
        scope_profile={"profile_name": "tenant"},
        retention_policy=override,
    )
    assert result == {"bundle_id": "bundle-1"}
    assert service.build_export_manifest.call_args.kwargs["node_id"] == "node-a"
    assert service.build_export_manifest.call_args.kwargs["retention"] == {
        "days": 7
    }

    economic.build_economic_audit_bundle(
        economic_audit_bundle_service=service,
        economic_memory_store=memory,
        roi_history_store=roi,
        economic_policy_snapshot_store=snapshots,
        economic_trace_store=traces,
        economic_metrics_store=metrics,
        economic_retention_policy=retention,
        economic_store_bundle=None,
        bundle_id="bundle-2",
    )
    assert service.build_export_manifest.call_args.kwargs["node_id"] == "local-primary"


def test_write_economic_bundle_handles_no_store_and_real_store():
    service = SimpleNamespace(write_bundle=Mock(return_value={"path": "/tmp/bundle"}))
    assert economic.write_economic_audit_bundle(
        economic_audit_bundle_service=service,
        economic_store_bundle=None,
        bundle_name="b",
        bundle={},
    ) == {"bundle_kind": "economic", "bundle_name": "b", "path": ""}

    store = SimpleNamespace(root_dir="/root", bundle_catalog_path="/catalog")
    result = economic.write_economic_audit_bundle(
        economic_audit_bundle_service=service,
        economic_store_bundle=store,
        bundle_name="b",
        bundle={"bundle_id": "id", "payload": {"x": 1}, "digest": "sha"},
    )
    assert result == {"path": "/tmp/bundle"}
    bundle_obj = service.write_bundle.call_args.kwargs["bundle"]
    assert bundle_obj.bundle_id == "id"
    assert bundle_obj.payload == {"x": 1}
    assert bundle_obj.digest == "sha"


def install_validator_fakes(monkeypatch, module, *, failure=None):
    values = {
        "migration": Verdict(supported=failure != "migration", reason="migration bad"),
        "monotonicity": Verdict(valid=failure != "monotonicity", reason="mono bad"),
        "lineage": Verdict(valid=failure != "lineage", reason="lineage bad"),
        "immutability": Verdict(valid=failure != "immutability", reason="immutable bad"),
    }
    monkeypatch.setattr(
        module,
        "EconomicSchemaValidator",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        module,
        "EconomicSchemaMigrationMatrix",
        lambda: SimpleNamespace(validate=lambda **kwargs: values["migration"]),
    )
    monkeypatch.setattr(
        module,
        "EconomicSegmentValidator",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        module,
        "EconomicSemanticValidator",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        module,
        "EconomicScopeLineageGuard",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        module,
        "EconomicReplayEpochGuard",
        lambda: SimpleNamespace(validate=lambda **kwargs: Verdict()),
    )
    monkeypatch.setattr(
        module,
        "EconomicStateMonotonicityGuard",
        lambda: SimpleNamespace(validate=lambda **kwargs: values["monotonicity"]),
    )
    monkeypatch.setattr(
        module,
        "EconomicLineageLockBuilder",
        lambda: SimpleNamespace(validate=lambda **kwargs: values["lineage"]),
    )
    monkeypatch.setattr(
        module,
        "EconomicBundleImmutabilityValidator",
        lambda: SimpleNamespace(validate=lambda **kwargs: values["immutability"]),
    )


def reconciliation_dependencies(*, consistent=True):
    rows = Rows({"row": 1})
    service = SimpleNamespace(
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
    builder = SimpleNamespace(
        build=Mock(
            return_value=DictObject(
                {
                    "consistent": consistent,
                    "metadata": {"quorum_failure_segments": ["roi"]},
                }
            )
        )
    )
    forensics = SimpleNamespace(record_event=Mock())
    return rows, service, builder, forensics


def call_economic_reconciliation(
    *, monkeypatch, bundle_entry=None, failure=None, consistent=True, store_bundle=None
):
    install_validator_fakes(monkeypatch, economic, failure=failure)
    rows, service, builder, forensics = reconciliation_dependencies(
        consistent=consistent
    )
    result = economic.build_economic_bundle_reconciliation(
        economic_audit_bundle_service=service,
        economic_multi_backend_reconciliation=builder,
        economic_forensics_service=forensics,
        economic_store_bundle=store_bundle,
        economic_memory_store=rows,
        roi_history_store=rows,
        economic_policy_snapshot_store=rows,
        economic_trace_store=rows,
        economic_metrics_store=rows,
        bundle={
            "bundle_id": "bundle",
            "digest": "sha",
            "payload": {
                "export_manifest": {
                    "scope": {"profile_name": "tenant"},
                    "bundle_schema_version": "1",
                }
            },
        },
        bundle_entry=bundle_entry,
    )
    return result, service, builder, forensics


def test_economic_reconciliation_in_memory_and_restored_success(monkeypatch):
    result, service, builder, forensics = call_economic_reconciliation(
        monkeypatch=monkeypatch, bundle_entry=None, consistent=True
    )
    assert result["import_validation"] == {
        "valid": True,
        "issues": [],
        "source": "in_memory_bundle",
    }
    service.restore_bundle.assert_not_called()
    assert forensics.record_event.call_args.kwargs["severity"] == "info"
    assert builder.build.call_args.kwargs["quorum_size"] == 2

    store_bundle = SimpleNamespace(node_id="node-a")
    restored, service, builder, forensics = call_economic_reconciliation(
        monkeypatch=monkeypatch,
        bundle_entry={"path": "/bundle.json"},
        consistent=False,
        store_bundle=store_bundle,
    )
    assert restored["import_validation"]["status"] == "valid"
    assert restored["import_validation"]["source"] == "bundle_restore"
    assert builder.build.call_args.kwargs["node_payloads"][0]["node_id"] == "node-a"
    assert forensics.record_event.call_args.kwargs["severity"] == "warning"


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("migration", "migration bad"),
        ("monotonicity", "mono bad"),
        ("lineage", "lineage bad"),
        ("immutability", "immutable bad"),
    ],
)
def test_economic_reconciliation_fails_closed_for_validator_rejection(
    monkeypatch, failure, message
):
    result, service, builder, forensics = call_economic_reconciliation(
        monkeypatch=monkeypatch,
        bundle_entry={"path": "/bundle.json"},
        failure=failure,
    )
    assert result["import_validation"]["valid"] is False
    assert message in result["import_validation"]["issues"][0]
    assert (
        builder.build.call_args.kwargs["node_payloads"][1]["payload"]["metadata"][
            "import_validation_status"
        ]
        == "invalid"
    )


def test_cross_run_audit_and_economic_payload_precedence():
    rows = Rows({"row": 1})
    audit = SimpleNamespace(build=Mock(return_value=DictObject({"ok": True})))
    assert economic.build_cross_run_economic_audit(
        cross_run_economic_audit=audit,
        economic_memory_store=rows,
        roi_history_store=rows,
        economic_policy_snapshot_store=rows,
    ) == {"ok": True}

    budget, revenue = economic.extract_economic_payload(
        action={
            "economic_safety": {
                "budget_guard": {"source": "action"},
                "revenue_verification": {"source": "action"},
            }
        },
        execution_receipt={"budget_guard": {"source": "receipt"}},
        verification={},
        persisted_payload={},
    )
    assert budget == {"source": "action"}
    assert revenue == {"source": "action"}

    budget, revenue = economic.extract_economic_payload(
        action={},
        execution_receipt={"budget_guard": {"source": "receipt"}},
        verification={},
        persisted_payload={},
    )
    assert budget == {"source": "receipt"}
    assert revenue == {}
    assert economic.extract_economic_payload(
        action={}, execution_receipt={}, verification={}, persisted_payload={}
    ) == ({}, {})
