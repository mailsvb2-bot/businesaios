from __future__ import annotations

from execution.business_memory_governance import BusinessMemoryGovernanceGate


def test_business_memory_governance_gate_approves_coherent_candidate() -> None:
    gate = BusinessMemoryGovernanceGate(min_fit_score=0.30)
    report = gate.evaluate(
        candidate_record={
            "goal": "increase revenue",
            "stop_reason": "goal_reached",
            "region": "eu",
            "channel": "headless",
            "final_feedback": {
                "goal_score": 0.91,
                "goal_reached": True,
                "retry_classification": {"kind": "success"},
            },
        },
        business_memory_summary={
            "active_goals": ["increase revenue"],
            "learned_preferences": {"region": "eu", "channel": "headless"},
            "recurring_failures": ["timeout"],
            "recurring_wins": ["goal_reached"],
        },
    )
    assert report.approved is True
    assert report.score >= 0.30
    assert "goal_matches_active_goal" in report.reasons


def test_business_memory_governance_gate_penalizes_repeated_failure() -> None:
    gate = BusinessMemoryGovernanceGate(min_fit_score=0.30)
    report = gate.evaluate(
        candidate_record={
            "goal": "increase revenue",
            "stop_reason": "execution_failed",
            "final_feedback": {
                "goal_score": 0.10,
                "error": "timeout",
                "retry_classification": {"kind": "operator_required"},
            },
        },
        business_memory_summary={
            "active_goals": ["increase revenue"],
            "learned_preferences": {},
            "recurring_failures": ["timeout"],
            "recurring_wins": [],
        },
    )
    assert report.approved is False
    assert "candidate_repeats_failure" in report.reasons



def test_business_memory_governance_gate_canonicalizes_raw_summary_before_scoring() -> None:
    gate = BusinessMemoryGovernanceGate(min_fit_score=0.30)
    report = gate.evaluate(
        candidate_record={
            "goal": "increase revenue",
            "stop_reason": "goal_reached",
            "region": "eu",
            "channel": "headless",
            "final_feedback": {
                "goal_score": 0.91,
                "goal_reached": True,
                "retry_classification": {"kind": "success"},
            },
        },
        business_memory_summary={
            "profile": {"segment": "services"},
            "active_goals": ["increase revenue", "increase revenue"],
            "learned_preferences": {"channel": "headless", "region": "eu"},
            "recurring_failures": [{"action": "timeout", "count": 2, "confidence": 0.7}],
            "recurring_wins": ["goal_reached", "goal_reached"],
            "blocked_actions": ["SEND_EMAIL"],
            "decision_hint": {"next_action": "launch_campaign"},
        },
    )
    assert report.approved is True
    assert report.score >= 0.30
    assert "goal_matches_active_goal" in report.reasons
    assert "channel_matches_preference" in report.reasons
    assert "region_matches_preference" in report.reasons
