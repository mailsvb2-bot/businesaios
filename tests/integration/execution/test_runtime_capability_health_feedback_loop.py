from __future__ import annotations

import pytest

ch_mod = pytest.importorskip("execution.capability_health_scoring")
planner_mod = pytest.importorskip("execution.capability_aware_planning")

CapabilityHealthScoringService = ch_mod.CapabilityHealthScoringService
FileCapabilityHealthStore = ch_mod.FileCapabilityHealthStore
CapabilityAwarePlanner = planner_mod.CapabilityAwarePlanner


def test_capability_health_runtime_snapshot_influences_planner(tmp_path) -> None:
    service = CapabilityHealthScoringService(
        store=FileCapabilityHealthStore(root_dir=tmp_path / "cap_health")
    )
    planner = CapabilityAwarePlanner()

    for _ in range(8):
        service.update_after_step(
            tenant_id="tenant-1",
            capability_key="launch_campaign",
            feedback={
                "executed": False,
                "verified": False,
                "self_healing_retry": {"reason": "transient_transport_failure"},
            },
        )

    runtime_snapshot = service.load_runtime_snapshot(
        tenant_id="tenant-1",
        capability_keys=["launch_campaign"],
    )

    class _State:
        meta = {"runtime_capabilities": runtime_snapshot}

    class _Request:
        autonomy_tier = "bounded_autonomy"
        meta = {}

    decision = planner.plan_action(
        request=_Request(),
        state=_State(),
        action_type="launch_campaign",
        payload={"estimated_cost": 3.0},
    )

    assert decision.reason in {
        "capability_ok",
        "degraded_mode_notify_owner",
        "low_health_score_notify_owner",
    }


def test_capability_health_runtime_snapshot_reports_health_fields(tmp_path) -> None:
    service = CapabilityHealthScoringService(
        store=FileCapabilityHealthStore(root_dir=tmp_path / "cap_health")
    )
    service.update_after_step(
        tenant_id="tenant-1",
        capability_key="notify_owner",
        feedback={
            "executed": True,
            "verified": True,
        },
    )

    snapshot = service.load_runtime_snapshot(
        tenant_id="tenant-1",
        capability_keys=["notify_owner"],
    )

    assert "notify_owner" in snapshot
    assert "health_score" in snapshot["notify_owner"]
    assert "verification_rate" in snapshot["notify_owner"]
    assert "success_rate" in snapshot["notify_owner"]


def test_persisted_risk_budget_forces_selected_capability_to_supervised(tmp_path) -> None:
    from application.autonomy.autonomy_decision_step import AutonomyDecisionStep
    from application.capability.capability_health_policy import CapabilityHealthPolicy
    from application.capability.capability_health_registry import CapabilityHealthRegistry
    from application.capability.capability_matrix import CapabilityMatrix

    store = FileCapabilityHealthStore(root_dir=tmp_path / "cap_health")
    registry = CapabilityHealthRegistry(
        store=store,
        matrix=CapabilityMatrix(),
        policy=CapabilityHealthPolicy(risk_budget_limit=1.0),
    )
    registry.update_after_feedback(
        tenant_id="tenant-1",
        action_type="launch_campaign",
        feedback={"executed": True, "verified": True, "risk_score": 0.6},
    )
    registry.update_after_feedback(
        tenant_id="tenant-1",
        action_type="launch_campaign",
        feedback={"executed": True, "verified": True, "risk_score": 0.5},
    )

    planner = CapabilityAwarePlanner(
        router=__import__(
            "application.capability.capability_router",
            fromlist=["ExecutionCapabilityRouter"],
        ).ExecutionCapabilityRouter(
            matrix=CapabilityMatrix(),
            health_registry=registry,
        )
    )

    class _State:
        meta = {}

    class _Request:
        tenant_id = "tenant-1"
        autonomy_tier = "full_autonomy"
        approval_policy = {}
        economy = {}
        constraints = {}
        meta = {}

    planned = planner.plan_action(
        request=_Request(),
        state=_State(),
        action_type="launch_campaign",
        payload={"estimated_cost": 1.0},
    )
    assert planned.capability["runtime"]["risk_budget_exceeded"] is True
    assert planned.capability["runtime"]["recommended_autonomy_tier"] == "supervised"

    effective = AutonomyDecisionStep._effective_autonomy_tier(
        requested_tier="full_autonomy",
        executable_action=type(
            "Action",
            (),
            {"payload": {"capability_planning": planned.to_dict()}},
        )(),
    )
    assert effective == "supervised"
