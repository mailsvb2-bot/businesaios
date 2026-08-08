from __future__ import annotations

import inspect

import pytest

from core.human_governance.contracts_deps import HumanGovernanceDeps
from core.human_governance.enums import RiskLevel, SalesHandoffReason
from core.human_governance.evaluators.sales_handoff import evaluate_sales_handoff
from core.human_governance.policy import HumanGovernancePolicy
from core.human_governance.service import HumanGovernanceService


def _policy() -> HumanGovernancePolicy:
    return HumanGovernancePolicy()


def _service() -> HumanGovernanceService:
    placeholder = object()
    return HumanGovernanceService(
        HumanGovernanceDeps(
            policy=_policy(),
            review_queue_reader=placeholder,
            approval_state_reader=placeholder,
            escalation_reader=placeholder,
            approval_writer=placeholder,
            rejection_writer=placeholder,
            override_writer=placeholder,
            pause_writer=placeholder,
            review_repository=placeholder,
            override_repository=placeholder,
        )
    )


def test_sensitive_context_and_explicit_request_precede_closed_subject() -> None:
    signal = evaluate_sales_handoff(
        policy=_policy(),
        tenant_id="tenant-a",
        subject_id="lead-1",
        model_confidence=0.99,
        explicit_human_request=True,
        sensitive_context=True,
        subject_closed=True,
        context={"conversation_id": "conv-1"},
    )
    assert signal is not None
    assert signal.reason == SalesHandoffReason.SENSITIVE_CONTEXT
    assert signal.risk_level == RiskLevel.CRITICAL
    assert signal.as_feature()["decision_authority"] is False
    assert signal.as_feature()["effect_authority"] is False


def test_closed_subject_does_not_handoff_only_for_low_confidence() -> None:
    assert evaluate_sales_handoff(
        policy=_policy(),
        tenant_id="tenant-a",
        subject_id="lead-2",
        model_confidence=0.10,
        subject_closed=True,
    ) is None


def test_policy_owned_thresholds_cover_failure_sentiment_and_confidence() -> None:
    policy = _policy()
    repeated = evaluate_sales_handoff(
        policy=policy,
        tenant_id="tenant-a",
        subject_id="lead-3",
        model_confidence=0.99,
        failed_attempts=policy.SALES_FAILURE_HANDOFF_THRESHOLD,
    )
    assert repeated is not None
    assert repeated.reason == SalesHandoffReason.REPEATED_FAILURE
    assert repeated.risk_level == RiskLevel.HIGH

    negative = evaluate_sales_handoff(
        policy=policy,
        tenant_id="tenant-a",
        subject_id="lead-4",
        model_confidence=0.99,
        negative_sentiment=True,
    )
    assert negative is not None
    assert negative.reason == SalesHandoffReason.NEGATIVE_SENTIMENT
    assert negative.risk_level == RiskLevel.MEDIUM

    low = evaluate_sales_handoff(
        policy=policy,
        tenant_id="tenant-a",
        subject_id="lead-5",
        model_confidence=policy.SALES_MIN_AUTOMATION_CONFIDENCE - 0.01,
    )
    assert low is not None
    assert low.reason == SalesHandoffReason.LOW_CONFIDENCE

    assert evaluate_sales_handoff(
        policy=policy,
        tenant_id="tenant-a",
        subject_id="lead-6",
        model_confidence=policy.SALES_MIN_AUTOMATION_CONFIDENCE,
    ) is None


def test_inputs_and_context_fail_closed() -> None:
    policy = _policy()
    with pytest.raises(ValueError, match="model_confidence"):
        evaluate_sales_handoff(
            policy=policy,
            tenant_id="tenant-a",
            subject_id="lead-1",
            model_confidence=float("nan"),
        )
    with pytest.raises(ValueError, match="failed_attempts"):
        evaluate_sales_handoff(
            policy=policy,
            tenant_id="tenant-a",
            subject_id="lead-1",
            model_confidence=0.9,
            failed_attempts=True,
        )
    with pytest.raises(ValueError, match="explicit_human_request"):
        evaluate_sales_handoff(
            policy=policy,
            tenant_id="tenant-a",
            subject_id="lead-1",
            model_confidence=0.9,
            explicit_human_request=1,
        )
    with pytest.raises(ValueError, match="JSON serializable"):
        evaluate_sales_handoff(
            policy=policy,
            tenant_id="tenant-a",
            subject_id="lead-1",
            model_confidence=0.1,
            context={"bad": object()},
        )
    with pytest.raises(ValueError, match="too large"):
        evaluate_sales_handoff(
            policy=policy,
            tenant_id="tenant-a",
            subject_id="lead-1",
            model_confidence=0.1,
            context={"blob": "x" * (33 * 1024)},
        )


def test_handoff_is_exposed_only_as_pure_human_governance_signal() -> None:
    service = _service()
    signal = service.evaluate_sales_handoff(
        tenant_id="tenant-a",
        subject_id="lead-7",
        model_confidence=0.2,
        context={"channel": "whatsapp"},
    )
    assert signal is not None
    assert signal.tenant_id == "tenant-a"
    assert signal.subject_id == "lead-7"
    source = inspect.getsource(evaluate_sales_handoff)
    forbidden = ("send_message", "RuntimeExecutor", "DecisionEnvelope", "effects.", "gateway.")
    assert all(token not in source for token in forbidden)
