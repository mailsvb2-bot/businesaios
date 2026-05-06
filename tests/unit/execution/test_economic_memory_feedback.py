from execution.economic_memory_feedback import EconomicMemoryFeedback


def test_economic_memory_feedback_accepts_direct_planning_signals() -> None:
    service = EconomicMemoryFeedback()
    record = service.build(
        action_type="launch_campaign",
        planning_signals={
            "channel": "ads",
            "action_type": "launch_campaign",
            "expected_roi": 0.4,
            "approved_budget": 100.0,
            "requested_budget": 120.0,
            "survival_mode": "normal",
            "operator_required": False,
        },
        revenue_verification_result={"verified": True, "revenue_amount": 250.0},
    )
    fact = record.to_memory_fact()
    assert fact["channel"] == "ads"
    assert fact["expected_roi"] == 0.4
    assert fact["realized_revenue"] == 250.0
    assert fact["efficiency_label"] == "verified_positive_roi"
