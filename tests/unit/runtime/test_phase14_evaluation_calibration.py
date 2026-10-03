from __future__ import annotations

import math

import pytest

from application.outcome import (
    BUSINESS_EVALUATION_METRICS,
    CalibrationEngine,
    EvaluationEngine,
)


def _outcome(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "outcome_id": "outcome:action-1",
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "run_id": "run-1",
        "intent_id": "intent-1",
        "decision_id": "decision-1",
        "action_id": "action-1",
        "action_type": "send_email",
        "goal": "grow",
        "status": "verified",
        "attempted": True,
        "executed": True,
        "verified": True,
        "goal_achieved": True,
        "goal_terminal": True,
        "completion_ratio": 0.75,
        "success_confidence": 0.05,
        "revenue_amount": 125.0,
        "revenue_verified": True,
        "metrics": {
            "margin": 35.0,
            "conversion_rate": 0.25,
            "retention_rate": 0.8,
            "actual_cost": 12.0,
            "latency_ms": 180.0,
            "complaint_count": 1.0,
            "human_override": False,
            "human_override_observed": True,
            "policy_violations": 0.0,
            "execution_failures": 0.0,
        },
    }
    payload.update(overrides)
    return payload


def _intent(*, confidence: object = 0.8) -> dict[str, object]:
    return {
        "schema_version": 2,
        "action_id": "action-1",
        "intent_id": "intent-1",
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "decision_id": "decision-1",
        "confidence": confidence,
    }


def test_phase14_evaluation_engine_covers_required_business_metrics() -> None:
    result = EvaluationEngine().evaluate(_outcome())

    assert tuple(result.metrics) == BUSINESS_EVALUATION_METRICS
    assert result.missing_metrics == ()
    assert result.metrics == {
        "revenue": 125.0,
        "margin": 35.0,
        "conversion": 0.25,
        "retention": 0.8,
        "goal_completion": 0.75,
        "cost": 12.0,
        "latency": 180.0,
        "complaints": 1.0,
        "human_override": 0.0,
        "policy_violations": 0.0,
        "execution_failures": 0.0,
    }


def test_phase14_evaluation_does_not_invent_zero_revenue_without_evidence() -> None:
    outcome = _outcome(
        revenue_amount=0.0,
        revenue_verified=False,
        metrics={},
    )

    result = EvaluationEngine().evaluate(outcome)

    assert "revenue" not in result.metrics
    assert "revenue" in result.missing_metrics
    assert result.metrics["goal_completion"] == 0.75
    assert result.metrics["execution_failures"] == 0.0


def test_phase14_calibration_uses_pre_action_confidence_not_posthoc_confidence() -> None:
    engine = CalibrationEngine()
    successful = engine.observation(
        outcome=_outcome(success_confidence=0.01),
        action_intent=_intent(confidence=0.8),
    )
    failed = engine.observation(
        outcome=_outcome(
            outcome_id="outcome:action-2",
            decision_id="decision-2",
            action_id="action-2",
            intent_id="intent-2",
            goal_achieved=False,
            success_confidence=0.99,
        ),
        action_intent={
            **_intent(confidence=0.6),
            "action_id": "action-2",
            "decision_id": "decision-2",
            "intent_id": "intent-2",
        },
    )

    assert successful is not None
    assert failed is not None
    assert successful.confidence == 0.8
    assert successful.success == 1.0
    assert failed.confidence == 0.6
    assert failed.success == 0.0

    report = engine.evaluate((successful, failed))
    assert report.sample_size == 2
    assert report.mean_confidence == pytest.approx(0.7)
    assert report.observed_success_rate == pytest.approx(0.5)
    assert report.calibration_error == pytest.approx(0.2)
    assert report.brier_score == pytest.approx(0.2)
    assert report.expected_calibration_error == pytest.approx(0.4)


def test_phase14_calibration_excludes_unresolved_outcomes() -> None:
    observation = CalibrationEngine.observation(
        outcome=_outcome(goal_terminal=False, goal_achieved=False),
        action_intent=_intent(confidence=0.9),
    )
    assert observation is None


def test_phase14_calibration_excludes_unattempted_terminal_outcomes() -> None:
    observation = CalibrationEngine.observation(
        outcome=_outcome(
            attempted=False,
            executed=False,
            goal_terminal=True,
            goal_achieved=False,
        ),
        action_intent=_intent(confidence=0.9),
    )
    assert observation is None


@pytest.mark.parametrize("confidence", [True, math.nan, math.inf, -0.1, 1.1])
def test_phase14_calibration_rejects_invalid_confidence(confidence: object) -> None:
    with pytest.raises(ValueError):
        CalibrationEngine.observation(
            outcome=_outcome(),
            action_intent=_intent(confidence=confidence),
        )


def test_phase14_calibration_rejects_lineage_mismatch() -> None:
    with pytest.raises(ValueError, match="decision_id conflicts"):
        CalibrationEngine.observation(
            outcome=_outcome(),
            action_intent={**_intent(), "decision_id": "forged"},
        )

    with pytest.raises(ValueError, match="action_type conflicts"):
        CalibrationEngine.observation(
            outcome=_outcome(),
            action_intent={
                **_intent(),
                "capability_target": "create_invoice",
            },
        )
