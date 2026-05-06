from execution.economic_policy_snapshot import EconomicPolicySnapshotBuilder
from execution.economic_risk_envelope import EconomicRiskEnvelopeBuilder
from observability.economic_policy_snapshot_store import InMemoryEconomicPolicySnapshotStore


def test_economic_risk_envelope_marks_high_risk_when_confidence_low_and_downside_negative() -> None:
    builder = EconomicRiskEnvelopeBuilder()
    envelope = builder.build(
        planning_signals={
            "economic_confidence": 0.2,
            "predicted_roi_floor": -0.4,
            "predicted_roi_ceiling": 0.6,
            "approved_budget": 100.0,
            "requested_budget": 150.0,
            "suggested_survival_mode": "survival",
            "operator_required": True,
        },
        spend_limits={"approved_budget": 100.0, "requested_budget": 150.0},
        economic_policy={"survival_mode": "survival", "operator_required": True},
    )
    payload = envelope.to_dict()
    assert payload["risk_level"] == "high"
    assert payload["requires_operator_review"] is True
    assert "negative_downside_roi" in payload["reasons"]


def test_economic_policy_snapshot_can_be_stored() -> None:
    builder = EconomicPolicySnapshotBuilder()
    snapshot = builder.build(
        snapshot_id="trace-1",
        budget_guard_result={
            "allowed": True,
            "operator_required": False,
            "reason": "budget_guard_allow",
            "spend_limits": {"requested_budget": 120.0, "approved_budget": 100.0},
            "economic_policy": {"survival_mode": "normal"},
            "metadata": {
                "action_type": "launch_campaign",
                "channel": "ads",
                "planning_signals": {"expected_roi": 0.4, "requested_budget": 120.0, "approved_budget": 100.0},
                "risk_envelope": {"risk_level": "medium"},
            },
        },
    )
    store = InMemoryEconomicPolicySnapshotStore()
    stored = store.append_payload(snapshot.to_dict())
    assert stored.to_dict()["snapshot_id"] == "trace-1"
    assert stored.to_dict()["risk_level"] == "medium"
